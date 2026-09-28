const encoder = new TextEncoder();
const bytes = value => typeof value === 'string' ? encoder.encode(value) : value;
const json = value => encoder.encode(JSON.stringify(value, null, 2));
const xmlEscape = value => String(value).replace(/[<>&"']/g, ch => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&apos;'}[ch]));
export function validateShapes(doc, shapes) {
  if (!Array.isArray(shapes) || shapes.length > 10000) throw Error('标注数量不合法');
  const ids = new Set();
  for (const s of shapes) {
    if (typeof s.id !== 'string' || !s.id || ids.has(s.id)) throw Error('标注 ID 重复或无效');
    ids.add(s.id);
    if (typeof s.label !== 'string' || !s.label.trim() || [...s.label].length > 200 || /[\x00-\x1f]/.test(s.label)) throw Error('文字不能留空或包含换行；无法释读请填写 □');
    const b = s.box;
    if (!Array.isArray(b) || b.length !== 4 || !b.every(Number.isFinite) || !(0 <= b[0] && b[0] < b[2] && b[2] <= doc.width && 0 <= b[1] && b[1] < b[3] && b[3] <= doc.height)) throw Error('矩形框超出图片范围或面积为零');
  }
}
function base64(data) {
  let binary = '';
  for (let i = 0; i < data.length; i += 32768) binary += String.fromCharCode(...data.subarray(i, i + 32768));
  return btoa(binary);
}
export function annotationFiles(doc, image, embed = false) {
  validateShapes(doc, doc.shapes);
  const {name:n, width:w, height:h, shapes} = doc;
  const labelme = {version:'5.5.0', flags:{}, shapes:shapes.map(s => ({label:s.label, points:[[s.box[0],s.box[1]],[s.box[2],s.box[3]]], group_id:null, description:'', shape_type:'rectangle', flags:{}})), imagePath:embed ? n+'.png' : '../intact-img/'+n+'.png', imageData:embed ? base64(image) : null, imageHeight:h, imageWidth:w};
  let start = 0;
  const spans = shapes.map((s,i) => {const end = start + [...s.label].length; const span = {coordinate_line:i+1,start,end,source_index:s.sourceIndex ?? null,id:s.id}; start=end; return span;});
  const objects = shapes.map(s => {
    const b=s.box, v=[Math.min(w,Math.floor(b[0])+1),Math.min(h,Math.floor(b[1])+1),Math.ceil(b[2]),Math.ceil(b[3])];
    return `<object><name>${xmlEscape(s.label)}</name><pose>Unspecified</pose><truncated>0</truncated><difficult>0</difficult><bndbox>${['xmin','ymin','xmax','ymax'].map((k,i)=>`<${k}>${v[i]}</${k}>`).join('')}</bndbox></object>`;
  }).join('\n');
  const xml=`<?xml version="1.0" encoding="utf-8"?>\n<annotation><folder>intact-img</folder><filename>${xmlEscape(n)}.png</filename><path>../intact-img/${xmlEscape(n)}.png</path><source><database>Silk_V2</database></source><size><width>${w}</width><height>${h}</height><depth>3</depth></size><segmented>0</segmented>\n${objects}\n</annotation>`;
  return new Map([
    [`annotations-json/${n}.json`, json(labelme)],
    [`annotations-xml/${n}.xml`, bytes(xml)],
    [`intact-img/${n}.png`, image],
    [`coordinate/${n}.txt`, bytes(shapes.map(s=>s.box.join(',')).join('\n')+(shapes.length?'\n':''))],
    [`gt-label/${n}.txt`, bytes(shapes.map(s=>s.label).join(''))],
    [`gt-index/${n}.json`, json({name:n,codepoint_count:start,spans})]
  ]);
}
const crcTable = new Uint32Array(256);
for(let n=0;n<256;n++){let c=n;for(let k=0;k<8;k++)c=c&1?0xedb88320^(c>>>1):c>>>1;crcTable[n]=c>>>0;}
function crc32(data){let c=0xffffffff;for(const b of data)c=crcTable[(c^b)&255]^(c>>>8);return (c^0xffffffff)>>>0;}
// ZIP STORE format; UTF-8 filenames and CRC checked by standard ZIP readers.
export function makeZip(entries) {
  const parts=[],directory=[];let offset=0,dirSize=0,count=0;
  for(const [filename,value] of entries){
    const name=encoder.encode(filename),data=bytes(value),crc=crc32(data);
    if(data.length>0xffffffff)throw Error('导出文件过大');
    const local=new Uint8Array(30),l=new DataView(local.buffer);
    l.setUint32(0,0x04034b50,true);l.setUint16(4,20,true);l.setUint16(6,0x800,true);l.setUint16(12,0x21,true);l.setUint32(14,crc,true);l.setUint32(18,data.length,true);l.setUint32(22,data.length,true);l.setUint16(26,name.length,true);
    parts.push(local,name,data);
    const central=new Uint8Array(46),c=new DataView(central.buffer);
    c.setUint32(0,0x02014b50,true);c.setUint16(4,20,true);c.setUint16(6,20,true);c.setUint16(8,0x800,true);c.setUint16(14,0x21,true);c.setUint32(16,crc,true);c.setUint32(20,data.length,true);c.setUint32(24,data.length,true);c.setUint16(28,name.length,true);c.setUint32(42,offset,true);
    directory.push(central,name);offset+=local.length+name.length+data.length;dirSize+=central.length+name.length;count++;
  }
  if(count>65535||offset+dirSize>0xffffffff)throw Error('导出内容超出 ZIP 限制');
  const end=new Uint8Array(22),e=new DataView(end.buffer);e.setUint32(0,0x06054b50,true);e.setUint16(8,count,true);e.setUint16(10,count,true);e.setUint32(12,dirSize,true);e.setUint32(16,offset,true);
  return new Blob([...parts,...directory,end],{type:'application/zip'});
}
export const exportReadme = 'Silk 标注导出\nannotations-json：LabelMe 矩形标注，0 起始像素边界，保留浮点坐标。\nannotations-xml：Pascal VOC，整数、1 起始闭区间；xmin/ymin=floor+1，xmax/ymax=ceil。\ncoordinate：与 JSON 一致，每行 xmin,ymin,xmax,ymax。\ngt-label：按框顺序连续拼接，无换行。\ngt-index：Unicode 码点区间与框顺序对应。\n公网版草稿只存于当前浏览器，请下载此文件包交回或备份；不会修改在线原始数据。\n';
