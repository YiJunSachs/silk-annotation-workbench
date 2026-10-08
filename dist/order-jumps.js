const median=a=>{const s=[...a].sort((a,b)=>a-b);return s.length%2?s[s.length>>1]:(s[s.length/2-1]+s[s.length/2])/2;};
// Candidate reading-order jumps, not a verdict about tables or separate fragments.
export function detectJumps(boxes,ids){
 if(ids.length<2)return [];
 const sh=ids.map(i=>boxes[i]),c=sh.map(s=>[(s.box[0]+s.box[2])/2,(s.box[1]+s.box[3])/2]),mw=median(sh.map(s=>s.box[2]-s.box[0])),mh=median(sh.map(s=>s.box[3]-s.box[1]));if(!(mw>0&&mh>0))return [];
 const slopes=[];
 for(const [ax,ay] of c){let best=Infinity,k;for(const [bx,by] of c){const dx=bx-ax,dy=by-ay;if(dy>.5*mh&&dy<2.2*mh&&Math.abs(dx)<.6*mw){const score=(Math.abs(dx)/mw)**2+(dy/mh-1.2)**2;if(score<best){best=score;k=dx/dy;}}}if(k!==undefined)slopes.push(k);}
 const slope=slopes.length?median(slopes):0,events=[];
 const add=(i,j,type)=>{if(!events.some(e=>e.from===ids[i]&&e.to===ids[j]))events.push({from:ids[i],to:ids[j],fromNumber:i+1,toNumber:j+1,type});};
 for(let i=0;i<sh.length-1;i++){const a=sh[i].box,b=sh[i+1].box,[x,y]=c[i],[xx,yy]=c[i+1],ax=x-slope*y,bx=xx-slope*yy,aw=a[2]-a[0],bw=b[2]-b[0],ah=a[3]-a[1],bh=b[3]-b[1];const overlap=Math.max(0,Math.min(ax+aw/2,bx+bw/2)-Math.max(ax-aw/2,bx-bw/2))/Math.min(aw,bw);
 if(overlap>=.55&&Math.abs(bx-ax)<=.45*mw&&y-yy>Math.max(.8*mh,.6*(ah+bh))&&y-yy<5*mh)add(i,i+1,'同列向上回跳');
 else if(xx-x>Math.max(2*mw,.9*(aw+bw))+.20*Math.abs(yy-y))add(i,i+1,'向右跨区');}
 const runs=[];let run=[0];for(let i=1;i<sh.length;i++){const dx=c[i][0]-c[i-1][0],dy=c[i][1]-c[i-1][1];if(dy>0&&dy<8*mh&&Math.abs(dx)<.7*mw+.12*dy)run.push(i);else{runs.push(run);run=[i];}}runs.push(run);
 for(let i=0;i<runs.length-1;i++){const a=runs[i],b=runs[i+1];if(a.length<4||b.length<4)continue;const ya=a.map(i=>c[i][1]),yb=b.map(i=>c[i][1]),lo=Math.max(Math.min(...ya),Math.min(...yb)),hi=Math.min(Math.max(...ya),Math.max(...yb));if(hi-lo<3*mh)continue;const yy=(hi+lo)/2;
 const fit=run=>{const mx=run.reduce((s,i)=>s+c[i][0],0)/run.length,my=run.reduce((s,i)=>s+c[i][1],0)/run.length,den=run.reduce((s,i)=>s+(c[i][1]-my)**2,0);const k=den?run.reduce((s,i)=>s+(c[i][0]-mx)*(c[i][1]-my),0)/den:0;return mx+k*(yy-my);};if(fit(b)-fit(a)>.65*mw)add(a[a.length-1],b[0],'反向换列');}
 return events.sort((a,b)=>a.fromNumber-b.fromNumber);
}
