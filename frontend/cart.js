/* Assistant cart: a saved selection, separate from the storefront checkout. */
(function (root) {
    const KEY = 'kiaasa_assistant_cart_v1';
    const money = value => '\u20b9' + value.toLocaleString('en-IN', {maximumFractionDigits: 2});
    function productUrl(value) {
        try {
            const url = new URL(value);
            if (url.protocol !== 'https:' || !['www.kiaasa.in','kiaasa.in','www.kiaasa.com','kiaasa.com'].includes(url.hostname) || !url.pathname.startsWith('/product/')) return null;
            url.search = ''; url.hash = '';
            return url.href;
        } catch { return null; }
    }
    class CartStore {
        constructor(storage) {
            this.storage = storage;
            this.items = [];
            this.saved = true;
            try {
                const data = JSON.parse(storage.getItem(KEY) || '[]');
                if (Array.isArray(data)) this.items = data.filter(item => item && productUrl(item.url) && typeof item.name === 'string' && typeof item.size === 'string' && item.size.length > 0 && item.size.length < 30 && item.key === productUrl(item.url) + '|' + item.size && Number.isFinite(item.price) && item.price >= 0 && Number.isInteger(item.quantity) && item.quantity >= 1 && item.quantity <= 99).slice(0,100);
            } catch { this.saved = false; }
        }
        persist() {
            try { this.storage.setItem(KEY, JSON.stringify(this.items)); this.saved = true; }
            catch { this.saved = false; }
        }
        add(product, size) {
            const url = productUrl(product.url);
            if (!url || !Array.isArray(product.sizes) || !product.sizes.includes(size) || !Number.isFinite(product.price) || product.price < 0 || /^(sold out|out of stock|unavailable)$/i.test(product.stock || '')) return false;
            const key = url + '|' + size;
            const existing = this.items.find(item => item.key === key);
            if (existing) {
                if (existing.quantity >= 99) return false;
                existing.quantity++; existing.price = product.price;
            } else {
                if (this.items.length >= 100) return false;
                this.items.push({key, url, name: product.display_name || product.name || 'Kiaasa product', size, price: product.price, quantity: 1});
            }
            this.persist(); return true;
        }
        change(key, quantity) {
            if (!Number.isInteger(quantity) || quantity < 0 || quantity > 99) return;
            this.items = this.items.filter(item => item.key !== key || quantity !== 0);
            const item = this.items.find(item => item.key === key);
            if (item) item.quantity = quantity;
            this.persist();
        }
        get count() { return this.items.reduce((sum, item) => sum + item.quantity, 0); }
        get total() { return this.items.reduce((sum, item) => sum + item.price * item.quantity, 0); }
    }
    if (typeof module !== 'undefined' && module.exports) module.exports = {CartStore, productUrl};
    if (typeof document === 'undefined') return;
    let storage;
    try { storage = localStorage; } catch { storage = {getItem(){return null;},setItem(){throw Error('Storage unavailable');}}; }
    const store = new CartStore(storage);
    const toggle = document.getElementById('cart-toggle');
    const panel = document.getElementById('assistant-cart');
    const messages = document.getElementById('chat-messages');
    const footer = document.querySelector('.chat-footer');
    let open = false;
    function el(tag, cls, text) {
        const node = document.createElement(tag); node.className = cls;
        if (text !== undefined) node.textContent = text;
        return node;
    }
    function button(text, label, handler) {
        const node = el('button', 'cart-control', text); node.type = 'button'; node.setAttribute('aria-label', label); node.addEventListener('click', handler); return node;
    }
    function render() {
        toggle.textContent = 'Cart (' + store.count + ')';
        panel.replaceChildren();
        panel.append(el('h2', 'cart-title', 'Your assistant cart'), el('p','cart-note','Saved here in this browser. These items have not been added to the Kiaasa website cart.'));
        if (!store.saved) panel.append(el('p','cart-note','Browser storage is unavailable. Your selection may be lost when you refresh.'));
        if (!store.items.length) panel.append(el('p','cart-empty','Your cart is empty. Choose a size on a product card to add an item.'));
        for (const item of store.items) {
            const row = el('article','cart-item');
            row.append(el('h3','', item.name), el('p','', 'Size: ' + item.size + ' ? ' + money(item.price)));
            const controls = el('div','cart-quantity');
            controls.append(button('-','Decrease quantity of '+item.name,()=>{store.change(item.key,item.quantity-1);render();}),el('span','',String(item.quantity)),button('+','Increase quantity of '+item.name,()=>{store.change(item.key,item.quantity+1);render();}),button('Remove','Remove '+item.name,()=>{store.change(item.key,0);render();}));
            row.append(controls);
            const checkout = el('a','cart-checkout','Continue on Kiaasa');
            checkout.href = productUrl(item.url); checkout.target = '_blank'; checkout.rel = 'noopener noreferrer';
            row.append(checkout,el('small','','Choose size '+item.size+' and add it to the website cart to checkout.'));
            panel.append(row);
        }
        if (store.items.length) panel.append(el('p','cart-total','Estimated subtotal: '+money(store.total)),el('p','cart-note','Final price, size availability, delivery and payment are confirmed on Kiaasa.'));
        panel.append(button('Continue shopping','Return to shopping',()=>setOpen(false)));
    }
    function setOpen(value) {
        open = value; panel.hidden = !open; messages.hidden = open; footer.hidden = open;
        toggle.setAttribute('aria-expanded',String(open));
        if (open) { render(); panel.focus(); } else { document.getElementById('message-input').focus(); }
    }
    toggle.addEventListener('click',()=>setOpen(!open));
    root.KiaasaCart = {
        attachControls(product, details, actions) {
            const url = productUrl(product.url);
            if (!url) return;
            const wrap = el('div','product-cart-controls');
            const available = Array.isArray(product.sizes) ? [...new Set(product.sizes.filter(s=>typeof s==='string' && s.length<30))] : [];
            const note = el('span','product-cart-feedback'); note.setAttribute('role','status');
            if (!available.length) {
                const link = el('a','cart-checkout','Choose size on Kiaasa'); link.href=url;link.target='_blank';link.rel='noopener noreferrer';link.className='add-to-cart-icon';link.title='Choose size on Kiaasa';link.setAttribute('aria-label','Choose size on Kiaasa');link.innerHTML="<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M2 3h3l2.5 12h11L21 7H6\"/><circle cx=\"9\" cy=\"20\" r=\"1\"/><circle cx=\"18\" cy=\"20\" r=\"1\"/></svg>";actions.append(link);
            } else {
                const label = el('label','cart-size-label','Select size');
                const select = el('select','product-size');select.setAttribute('aria-label','Size for '+(product.display_name || product.name));
                const placeholder = el('option','','Choose size');placeholder.value='';select.append(placeholder);
                available.forEach(size=>{const option=el('option','',size);option.value=size;select.append(option);});
                label.append(select);
                const add = button('','Add '+(product.display_name || product.name)+' to cart',()=>{
                    if (!select.value) {note.textContent='Please choose a size.';select.focus();return;}
                    if (store.add(product,select.value)) {render();note.textContent=store.saved?'Added to your assistant cart.':'Added for this visit; browser storage is unavailable.';} else note.textContent='Unable to add this selection. Check availability on Kiaasa.';
                });
                add.className='add-to-cart-icon';
                add.title='Add to assistant cart';
                add.innerHTML="<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M2 3h3l2.5 12h11L21 7H6\"/><circle cx=\"9\" cy=\"20\" r=\"1\"/><circle cx=\"18\" cy=\"20\" r=\"1\"/></svg>";
                wrap.append(label);
                actions.append(add);
            }
            wrap.append(note);details.append(wrap);
        }
    };
    render();
})(typeof window !== 'undefined' ? window : globalThis);
