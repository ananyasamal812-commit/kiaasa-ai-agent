const API_URL = location.protocol === "file:" || (["localhost", "127.0.0.1"].includes(location.hostname) && location.port === "5500") ? "http://127.0.0.1:8000/chat" : new URL("api/chat", document.baseURI).href;


// A freshly loaded page starts a new conversation, with no previous user's filters.
let sessionId = crypto.randomUUID();
let sessionToken = '';
let sessionInitialization = null;
async function ensureChatSession() {
    if (sessionToken) return;
    if (!sessionInitialization) sessionInitialization = (async () => {
        const response = await fetch(API_URL.replace(/\/chat$/, '/session'), {
            method: 'POST', signal: AbortSignal.timeout(10000)
        });
        if (!response.ok) throw new Error('Unable to start chat session');
        const data = await response.json();
        sessionId = data.session_id;
        sessionToken = data.session_token;
    })().catch(error => { sessionInitialization = null; throw error; });
    await sessionInitialization;
}
const initialWelcome = document.querySelector('.welcome-message');
const initialMenu = document.getElementById('shopping-menu');


// Open / close chat
function toggleChat() {

    const chat =
        document.getElementById("chat-container");

    chat.classList.toggle("chat-hidden");
    dismissWelcome();
    const isOpen = !chat.classList.contains("chat-hidden");
    document.getElementById("chat-button").setAttribute("aria-expanded", String(isOpen));
    document.getElementById("chat-button").setAttribute("aria-label", isOpen ? "Close shopping assistant" : "Open shopping assistant");
    if (isOpen) document.getElementById("message-input").focus();
}

function dismissWelcome() {
    document.getElementById("welcome-popup").hidden = true;
}

function openChat() {
    document.getElementById("chat-container").classList.add("chat-hidden");
    toggleChat();
}

document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
        dismissWelcome();
        const chat = document.getElementById("chat-container");
        if (!chat.classList.contains("chat-hidden")) {
            toggleChat();
            document.getElementById("chat-button").focus();
        }
    }
});


let messagePending = false;

// Send message
async function sendMessage(action = null) {

    const input =
        document.getElementById("message-input");

    const message =
        input.value.trim();

    if (!message || messagePending) {
        return;
    }


    messagePending = true;
    document.getElementById("shopping-menu").hidden = true;
    document.querySelector(".welcome-message").hidden = true;
    addUserMessage(message);

    input.value = "";


    const loadingMessage =
        addBotMessage("Typing...");


    try {
        await ensureChatSession();
        const response =
            await fetch(API_URL, {
                signal: AbortSignal.timeout(35000),

                method: "POST",

                headers: {
                    "Content-Type": "application/json",
                    "X-Session-Token": sessionToken
                },

                body: JSON.stringify({
                    message: message,
                    session_id: sessionId,
                    action: action
                })
            });


        const data =
            await response.json();


        if (!response.ok) {

            loadingMessage.innerText =
                response.status === 429 ? 'Too many requests. Please wait a minute and try again.' :
                response.status === 401 ? 'Your session expired. Refresh this page to start again.' :
                (typeof data.detail === 'string' ? data.detail : 'Please check your message and try again.');

            return;
        }


        document.getElementById("collection-switcher").hidden = !['collection', 'shopping', 'product_details'].includes(data.intent);

        if (data.show_menu) {
            const messages = document.getElementById('chat-messages');
            initialWelcome.innerText = data.reply;
            initialWelcome.hidden = false;
            initialMenu.hidden = false;
            messages.replaceChildren(initialWelcome, initialMenu);
            messages.scrollTop = 0;
            return;
        }

        // Show the catalogue-grounded reply.
        loadingMessage.innerText =
            data.reply;

        if (data.intent === "order_tracking" && Array.isArray(data.tracking)) {
            data.tracking.forEach(shipment => addTrackingCard(shipment));
        }

        if (Array.isArray(data.links) || Array.isArray(data.suggestions)) {
            addResponseActions(data.links || [], data.suggestions || []);
        }


        // Show matched product cards
        if (
            data.intent !== "order_tracking" &&
            data.products &&
            data.products.length > 0
        ) {

            if (data.intent === "collection") {
                addCollectionProducts(data.products);
            } else data.products.forEach(
                product => {
                    addProductCard(product);
                }
            );
        }


    } catch (error) {

        loadingMessage.innerText =
            "Sorry, I'm having trouble connecting right now.";

        console.error(error);
    } finally {
        messagePending = false;
    }
}


function quickCollection(collection) {
    if (messagePending) return;
    const labels = {new_arrivals: 'Show me new arrivals', festive: 'Help me find festive wear', everyday: 'Help me find everyday styles'};
    document.getElementById('message-input').value = labels[collection];
    sendMessage(collection);
}

function startNewConversation() {
    if (messagePending) return;
    sessionId = crypto.randomUUID();
    document.getElementById('message-input').value = 'Start over';
    sendMessage('reset');
}

function addResponseActions(links, suggestions) {
    const actions = document.createElement('div');
    actions.className = 'response-actions';
    for (const item of links) {
        const url = safeProductUrl(item.url);
        if (!url) continue;
        const link = document.createElement('a');
        link.textContent = item.label;
        link.href = url;
        if (new URL(url).origin !== location.origin) {
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
        }
        actions.appendChild(link);
    }
    for (const suggestion of suggestions) {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = suggestion;
        button.addEventListener('click', () => quickMessage(suggestion));
        actions.appendChild(button);
    }
    document.getElementById('chat-messages').appendChild(actions);
}

// All collection products are fetched; render a few at a time to keep chat usable.
function addCollectionProducts(products) {
    const messages = document.getElementById('chat-messages');
    let offset = 0;
    const more = document.createElement('button');
    more.className = 'collection-load-more';
    more.type = 'button';
    function showBatch() {
        more.remove();
        products.slice(offset, offset + 12).forEach(addProductCard);
        offset = Math.min(offset + 12, products.length);
        if (offset < products.length) {
            more.textContent = `Show more styles (${offset} of ${products.length} shown)`;
            messages.appendChild(more);
        }
    }
    more.addEventListener('click', showBatch);
    showBatch();
}

// Quick buttons
function quickMessage(message) {

    document.getElementById(
        "message-input"
    ).value = message;

    sendMessage();
}


// Add customer message
function addUserMessage(message) {

    const messages =
        document.getElementById(
            "chat-messages"
        );


    const div =
        document.createElement("div");


    div.className =
        "user-message";


    div.innerText =
        message;


    messages.appendChild(div);


    messages.scrollTop =
        messages.scrollHeight;
}


// Add AI message
function addBotMessage(message) {

    const messages =
        document.getElementById(
            "chat-messages"
        );


    const div =
        document.createElement("div");


    div.className =
        "bot-message";


    div.innerText =
        message;


    messages.appendChild(div);


    messages.scrollTop =
        messages.scrollHeight;


    return div;
}


// Render catalogue values through DOM properties to keep text and URLs safe.
function safeProductUrl(value) {
    if (!value) return null;
    try {
        const parsed = new URL(value, window.location.href);
        return ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : null;
    } catch { return null; }
}

function addTrackingCard(shipment, autoRefresh = true) {
    const messages = document.getElementById('chat-messages');
    const card = document.createElement('section');
    card.className = 'tracking-card';
    card.setAttribute('aria-label', 'Shipment tracking');
    const title = document.createElement('h3');
    title.textContent = shipment.status || 'Shipment update';
    card.appendChild(title);
    const details = document.createElement('dl');
    for (const [key, label] of [['awb', 'Tracking number'], ['courier', 'Courier'], ['latest_location', 'Latest scanned location'], ['location_updated_at', 'Location updated'], ['estimated_delivery', 'Estimated delivery'], ['delivered_at', 'Delivered']]) {
        if (!shipment[key]) continue;
        const term = document.createElement('dt');
        term.textContent = label;
        const value = document.createElement('dd');
        value.textContent = String(shipment[key]);
        details.append(term, value);
    }
    card.appendChild(details);
    const locationNote = document.createElement('p');
    locationNote.className = 'tracking-location-note';
    locationNote.textContent = shipment.latest_location ? 'Location from the latest courier scan. Updates appear when the courier scans your shipment.' : 'The courier has not reported a scan location yet.';
    card.appendChild(locationNote);
    if (Array.isArray(shipment.activities) && shipment.activities.length) {
        const list = document.createElement('ol');
        list.className = 'tracking-events';
        for (const event of shipment.activities) {
            const item = document.createElement('li');
            const activity = document.createElement('span');
            activity.textContent = event.activity;
            const date = document.createElement('small');
            date.textContent = event.date;
            item.append(activity, date);
            if (event.location) {
                const scanLocation = document.createElement('small');
                scanLocation.textContent = event.location;
                item.appendChild(scanLocation);
            }
            list.appendChild(item);
        }
        card.appendChild(list);
    }
    const url = safeProductUrl(shipment.tracking_url);
    if (url && new URL(url).protocol === 'https:' && ['app.shiprocket.in', 'shiprocket.in', 'www.shiprocket.in', 'tracking.shiprocket.in'].includes(new URL(url).hostname)) {
        const link = document.createElement('a');
        link.href = url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = 'View live tracking';
        card.appendChild(link);
    }
    if (autoRefresh) {
        messages.appendChild(card);
        messages.scrollTop = messages.scrollHeight;
        if (shipment.awb) startTrackingRefresh(card, shipment);
    }
    return card;
}

function addProductCard(product) {
    const messages = document.getElementById('chat-messages');
    const card = document.createElement('div');
    card.className = 'product-card';
    const fullName = product.name || 'Kiaasa Product';
    const name = product.display_name || fullName.split('|')[0].trim();
    const imageUrl = product.image_unavailable ? null : safeProductUrl(product.image_url || product.image || PRODUCT_IMAGES[fullName]);
    const media = document.createElement('div');
    media.className = 'product-media';
    const unavailable = document.createElement('span');
    unavailable.className = 'product-image-unavailable';
    unavailable.textContent = 'Image unavailable';
    unavailable.hidden = Boolean(imageUrl);
    media.appendChild(unavailable);
    if (imageUrl) {
        const image = document.createElement('img');
        image.className = 'product-image';
        image.alt = name;
        image.loading = 'lazy';
        image.decoding = 'async';
        image.addEventListener('error', () => {
            image.hidden = true;
            unavailable.hidden = false;
        }, { once: true });
        image.src = imageUrl;
        media.appendChild(image);
    }
    card.appendChild(media);
    const details = document.createElement('div');
    details.className = 'product-details';
    const title = document.createElement('div');
    title.className = 'product-name';
    title.textContent = name;
    title.title = fullName;
    details.appendChild(title);
    const prices = document.createElement('div');
    prices.className = 'product-price-row';
    const currency = value => '\u20b9' + Number(value).toLocaleString('en-IN');
    for (const [key, cls] of [['price', 'product-price'], ['original_price', 'original-price']]) {
        if (product[key] != null && Number.isFinite(Number(product[key]))) {
            const price = document.createElement('span');
            price.className = cls;
            price.textContent = currency(product[key]);
            prices.appendChild(price);
        }
    }
    details.appendChild(prices);
    for (const [key, label] of [['color', 'Colour'], ['fabric', 'Fabric'], ['style', 'Style']]) {
        if (product[key]) {
            const info = document.createElement('div');
            info.className = 'product-info';
            info.textContent = label + ': ' + product[key];
            details.appendChild(info);
        }
    }
    if (Array.isArray(product.sizes) && product.sizes.length) {
        const sizes = document.createElement('div');
        sizes.className = 'product-info';
        sizes.textContent = 'Listed sizes: ' + product.sizes.join(', ');
        details.appendChild(sizes);
    }
    if (Array.isArray(product.match_reasons) && product.match_reasons.length) {
        const reasons = document.createElement('div');
        reasons.className = 'product-match-reasons';
        reasons.textContent = product.match_reasons.join(' · ');
        details.appendChild(reasons);
    }
    const actions = document.createElement('div');
    actions.className = 'product-card-actions';
    const productUrl = safeProductUrl(product.url);
    if (productUrl) {
        const link = document.createElement('a');
        link.href = productUrl;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.className = 'view-product-btn';
        link.textContent = 'View Product';
        actions.appendChild(link);
    }
    KiaasaCart.attachControls(product, details, actions);
    details.appendChild(actions);
    card.appendChild(details);
    messages.appendChild(card);
    messages.scrollTop = messages.scrollHeight;
}

// Send message when Enter is pressed
document
    .getElementById("message-input")
    .addEventListener(
        "keypress",
        function(event) {

            if (event.key === "Enter") {

                event.preventDefault();

                sendMessage();
            }
        }
    );


function startTrackingRefresh(initialCard, shipment) {
    let card = initialCard;
    let pending = false;
    let failures = 0;
    let stopped = false;
    const controls = document.createElement('div');
    controls.className = 'tracking-refresh-controls';
    const checked = document.createElement('small');
    const refresh = document.createElement('button');
    refresh.type = 'button';
    refresh.textContent = 'Refresh now';
    const terminal = value => /^(delivered|cancelled|canceled|rto delivered|lost)$/i.test(String(value || '').trim());
    function checkedText(status) {
        checked.textContent = `Checked at ${new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'})}. ${terminal(status) ? 'Shipment completed.' : 'Automatically checks every 60 seconds while this chat is open.'}`;
    }
    checkedText(shipment.status);
    controls.append(checked, refresh);
    card.appendChild(controls);
    async function update(manual = false) {
        if (!card.isConnected) { clearInterval(timer); return; }
        if (pending || (!manual && (stopped || document.hidden || document.getElementById('chat-container').classList.contains('chat-hidden')))) return;
        pending = true;
        refresh.disabled = true;
        checked.textContent = 'Checking courier updates...';
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 25000);
        try {
            const response = await fetch(API_URL.replace(/\/chat$/, '/tracking/') + encodeURIComponent(shipment.awb), {cache: 'no-store', signal: controller.signal, headers: {'X-Session-Token': sessionToken}});
            if (!response.ok) throw new Error('Tracking request failed');
            const data = await response.json();
            const updated = Array.isArray(data.tracking) && data.tracking.find(item => item.awb === shipment.awb);
            if (!updated) throw new Error('No shipment update');
            if (!card.isConnected) return;
            const replacement = addTrackingCard(updated, false);
            replacement.appendChild(controls);
            card.replaceWith(replacement);
            card = replacement;
            failures = 0;
            stopped = terminal(updated.status);
            checkedText(updated.status);
        } catch {
            failures++;
            stopped = failures >= 3;
            checked.textContent = stopped ? 'Automatic checks paused after repeated errors. Your last shipment update is still shown. Try Refresh now.' : 'Could not fetch a new update. Your last shipment update is still shown; retrying in 60 seconds.';
        } finally {
            clearTimeout(timeout);
            pending = false;
            refresh.disabled = false;
        }
    }
    stopped = terminal(shipment.status);
    const timer = setInterval(() => update(), 60000);
    refresh.addEventListener('click', () => update(true));
}

// Static markup uses data attributes so production can disallow inline scripts.
document.addEventListener('click', event => {
    const control = event.target.closest('[data-chat-action], [data-collection], [data-message]');
    if (!control) return;
    if (control.dataset.collection) quickCollection(control.dataset.collection);
    else if (control.dataset.message) quickMessage(control.dataset.message);
    else {
        const actions = {dismissWelcome, toggleChat, openChat, sendMessage: () => sendMessage()};
        const action = actions[control.dataset.chatAction];
        if (action) action();
    }
});
