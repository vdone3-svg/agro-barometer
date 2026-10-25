const root=document.getElementById('v13-news-body');
const msg=document.getElementById('v13-news-state');
const dateFmt=new Intl.DateTimeFormat('uk-UA',{day:'2-digit',month:'2-digit',year:'numeric'});
const cropNames=['пшениця','кукурудза','соняшник','ячмінь','соя','ріпак'];
function text(tag,value){const n=document.createElement(tag);n.textContent=value;return n}
try{
 const res=await fetch('/.netlify/functions/news-digest',{cache:'no-store'});
 if(!res.ok)throw Error('Помилка джерела');const data=await res.json();
 const ok=data.status==='news_context_available';
 msg.textContent=ok?`Новинне зведення станом на ${dateFmt.format(new Date(data.generated_at))}. Перевіряємо публікації за останні 14 днів. RSS-стрічок доступно: ${data.sources.filter(s=>s.ok).length} із ${data.sources.length}; незалежних видань серед доступних: ${new Set(data.sources.filter(s=>s.ok).map(s=>s.publisher)).size}. У каталозі: ${data.source_catalog?.publishers_total||0} видань і організацій (інші очікують інтеграції).`:'Зараз не вдалося отримати актуальні новини. Не робимо висновків щодо руху цін.';
 root.replaceChildren();
 for(const crop of cropNames){const d=data.crops?.[crop];const section=document.createElement('section');section.style.cssText='padding:12px 0;border-bottom:1px solid #dae5dd';
 const h=text('h4',crop[0].toLocaleUpperCase('uk-UA')+crop.slice(1));h.style.margin='0 0 6px';section.append(h);
 const p=text('p',d?.summary||'Дані недоступні.');p.style.margin='3px 0 8px';section.append(p);
 const ul=document.createElement('ul');ul.style.cssText='margin:0;padding-left:20px';
 for(const a of d?.articles||[]){let url;try{url=new URL(a.url)}catch{continue}if(url.protocol!=='https:')continue;
 const li=document.createElement('li');li.style.margin='5px 0';const link=document.createElement('a');link.href=url.toString();link.target='_blank';link.rel='noopener noreferrer';link.textContent=a.title;li.append(link,text('small',` — ${a.source}, ${dateFmt.format(new Date(a.date))}`));ul.append(li)}
 section.append(ul);root.append(section)
 }
}catch{msg.textContent='Новинне джерело недоступне. Підсумок не оновлено — жодних припущень про стан цін.'}
