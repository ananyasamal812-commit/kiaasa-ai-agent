const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {CartStore,productUrl}=require('../cart.js');
const values=new Map();
const storage={getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v)};
const product={name:'Test kurta',url:'https://www.kiaasa.in/product/test',price:1500,sizes:['M','L']};
let store=new CartStore(storage);
assert(!store.add(product,''));assert(!store.add(product,'XL'));
assert(store.add(product,'M'));assert(store.add(product,'M'));assert(store.add(product,'L'));
assert.equal(store.count,3);assert.equal(store.total,4500);assert.equal(store.items.length,2);
store=new CartStore(storage);assert.equal(store.count,3);
store.change(store.items[0].key,1);assert.equal(store.total,3000);
store.change(store.items[0].key,0);assert.equal(store.count,1);
assert(!store.add({...product,stock:'Sold out'},'M'));
assert.equal(productUrl('javascript:alert(1)'),null);
assert.equal(productUrl('https://evil.example/product/test'),null);
store=new CartStore({getItem:()=>'{bad',setItem(){throw Error('unavailable')}});
assert(store.add(product,'M'));assert.equal(store.saved,false);
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.events={};this.hidden=false;this.value='';}
 append(...nodes){this.children.push(...nodes);}
 appendChild(node){this.append(node);}
 replaceChildren(...nodes){this.children=nodes;}
 setAttribute(k,v){this[k]=v;}
 addEventListener(k,fn){this.events[k]=fn;}
 focus(){this.focused=true;}
}
const ids=Object.fromEntries(['cart-toggle','assistant-cart','chat-messages','message-input'].map(id=>[id,new Element('div')]));
const footer=new Element('footer');
const document={getElementById:id=>ids[id],querySelector:()=>footer,createElement:t=>new Element(t)};
const window={};
vm.runInNewContext(fs.readFileSync(require.resolve('../cart.js'),'utf8'),{window,document,URL,localStorage:{getItem:()=>null,setItem(){}}});
const details=new Element('div'),actions=new Element('div');window.KiaasaCart.attachControls(product,details,actions);
const controls=details.children[0],select=controls.children[0].children[0],add=actions.children[0];
add.events.click();assert.equal(ids['cart-toggle'].textContent,'Cart (0)');
select.value='M';add.events.click();assert.equal(ids['cart-toggle'].textContent,'Cart (1)');
ids['cart-toggle'].events.click();assert.equal(ids['assistant-cart'].hidden,false);assert.equal(ids['chat-messages'].hidden,true);
const back=ids['assistant-cart'].children.at(-1);back.events.click();assert.equal(ids['assistant-cart'].hidden,true);assert.equal(ids['chat-messages'].hidden,false);assert.equal(footer.hidden,false);
console.log('PASS: cart variants, persistence, totals, removal, validation, unavailable stock/storage, product controls, size requirement, badge and cart navigation.');
