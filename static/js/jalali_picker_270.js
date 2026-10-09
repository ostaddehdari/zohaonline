(function(){
  const months=['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
  const fa=n=>String(n).replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
  const toEn=s=>String(s||'').replace(/[۰-۹]/g,d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d));
  const div=(a,b)=>Math.floor(a/b);
  function g2j(gy,gm,gd){const gdm=[0,31,59,90,120,151,181,212,243,273,304,334],gy2=gy+(gm>2?1:0);let days=355666+365*gy+div(gy2+3,4)-div(gy2+99,100)+div(gy2+399,400)+gd+gdm[gm-1],jy=-1595+33*div(days,12053);days%=12053;jy+=4*div(days,1461);days%=1461;if(days>365){jy+=div(days-1,365);days=(days-1)%365;}return days<186?[jy,1+div(days,31),1+days%31]:[jy,7+div(days-186,30),1+(days-186)%30];}
  function leap(jy){const a=jy>0?474:473,b=474+((a%2820)+2820)%2820;return (((b+38)*682)%2816)<682;}
  function mdays(y,m){return m<=6?31:m<=11?30:(leap(y)?30:29)}
  function parse(v){const p=toEn(v).replace(/[-.]/g,'/').split('/').map(Number);return p.length===3&&p.every(Boolean)?p:null}
  function pad(n){return String(n).padStart(2,'0')}
  let active=null, y=0,m=0;
  const pop=document.createElement('div');pop.className='jalali-popover';pop.hidden=true;document.body.appendChild(pop);
  function close(){pop.hidden=true;active=null}
  function render(){const count=mdays(y,m);pop.innerHTML=`<div class="jp-head"><button type="button" data-jp-next>‹</button><strong>${months[m-1]} ${fa(y)}</strong><button type="button" data-jp-prev>›</button></div><div class="jp-week"><span>ش</span><span>ی</span><span>د</span><span>س</span><span>چ</span><span>پ</span><span>ج</span></div><div class="jp-days">${Array.from({length:count},(_,i)=>`<button type="button" data-day="${i+1}">${fa(i+1)}</button>`).join('')}</div><div class="jp-foot"><button type="button" data-jp-today>امروز</button><button type="button" data-jp-clear>پاک کردن</button></div>`;
    pop.querySelector('[data-jp-prev]').onclick=()=>{m--;if(m<1){m=12;y--}render()};pop.querySelector('[data-jp-next]').onclick=()=>{m++;if(m>12){m=1;y++}render()};
    pop.querySelectorAll('[data-day]').forEach(b=>b.onclick=()=>{active.value=`${y}/${pad(m)}/${pad(+b.dataset.day)}`;active.dispatchEvent(new Event('change',{bubbles:true}));close()});
    pop.querySelector('[data-jp-today]').onclick=()=>{const d=new Date(),j=g2j(d.getFullYear(),d.getMonth()+1,d.getDate());active.value=`${j[0]}/${pad(j[1])}/${pad(j[2])}`;close()};pop.querySelector('[data-jp-clear]').onclick=()=>{active.value='';close()};
  }
  function open(input){active=input;const p=parse(input.value),now=new Date(),j=p||g2j(now.getFullYear(),now.getMonth()+1,now.getDate());[y,m]=j;render();const r=input.getBoundingClientRect();pop.style.top=(window.scrollY+r.bottom+6)+'px';pop.style.left=Math.max(8,Math.min(window.scrollX+r.left,window.innerWidth-pop.offsetWidth-8))+'px';pop.hidden=false;}
  document.querySelectorAll('[data-jalali-picker]').forEach(input=>{input.type='text';input.placeholder=input.placeholder||'۱۴۰۵/۰۵/۲۸';input.autocomplete='off';input.addEventListener('focus',()=>open(input));input.addEventListener('click',()=>open(input));});
  document.addEventListener('mousedown',e=>{if(!pop.hidden&&!pop.contains(e.target)&&e.target!==active)close()});
})();
