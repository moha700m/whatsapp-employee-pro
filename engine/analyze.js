// Organizes chats into customers/orders with local Arabic heuristics (no external AI).
const ORDER_RE=/(ورد|ورود|باقة|بوكيه|بوكية|طلب|ابغى|ابي|أبي|ابغي|توصيل|هدية|تنسيق|سعر|بكم|كم سعر|جوري|توليب|زهور|حجز)/;
const DONE_RE=/(تم التوصيل|وصل|استلمت|شكرا|مشكور|تسلم|يعطيك العافية)/;
const FLOWERS=['جوري','توليب','ليليوم','أوركيد','اوركيد','عباد الشمس','قرنفل','بيبي روز','هيدرانجا','باقة','بوكيه','تنسيق','مزهرية'];
function textOf(m){return m.text||''}
export function heuristic(chats){
  const customers=chats.filter(c=>!c.isGroup).map(c=>{
    const msgs=[...c.messages].sort((a,b)=>a.ts-b.ts);
    const inc=msgs.filter(m=>!m.fromMe);
    const all=msgs.map(textOf).join(' \n ');
    const last=msgs[msgs.length-1];
    const items=FLOWERS.filter(f=>all.includes(f));
    const isOrder=ORDER_RE.test(inc.map(textOf).join(' '));
    const done=DONE_RE.test(msgs.slice(-4).map(textOf).join(' '));
    const unanswered=!!last&&!last.fromMe&&!DONE_RE.test(textOf(last))&&!/^(تمام|اوك|ok|طيب|زين)\s*$/i.test(textOf(last).trim());
    const orderMsgs=inc.filter(m=>ORDER_RE.test(textOf(m))).map(textOf);
    return {name:c.name||'',phone:c.phone,messages:msgs.length,lastAt:last?.ts||0,
      order:isOrder?(orderMsgs.slice(-2).join(' | ').slice(0,200)||items.join('، ')):'',
      items,status:!isOrder?'استفسار':(done?'مكتمل':'معلق'),unanswered,
      lastMessage:(last?textOf(last):'').slice(0,140),note:''};
  }).sort((a,b)=>b.lastAt-a.lastAt);
  return summarize(customers,'ترتيب تلقائي محلي');
}
function summarize(customers,engine,ai){
  const pending=customers.filter(c=>c.status==='معلق'),un=customers.filter(c=>c.unanswered);
  return {engine,generatedAt:Date.now(),customers,
    stats:{customers:customers.length,orders:customers.filter(c=>c.order).length,pending:pending.length,unanswered:un.length},
    summary:ai||`عندك ${customers.length} عميل، منهم ${customers.filter(c=>c.order).length} عندهم طلبات. الطلبات المعلقة: ${pending.length}. محادثات ما انرد عليها: ${un.length}.`};
}
export async function analyze(chats){return heuristic(chats)}
