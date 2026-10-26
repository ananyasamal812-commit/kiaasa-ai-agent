"""Grounded shopping conversations: explicit preferences are hard filters."""
import copy
import re

WELCOME = "Hi! Welcome to Kiaasa. What are you shopping for today—festive wear, everyday styles, or something for work? You can also browse new arrivals, find a store, or track an order."
COLORS = ['off white', 'navy blue', 'powder blue', 'light blue', 'light brown', 'rama green', 'teal blue', 'sage green', 'pista green', 'olive green', 'red', 'maroon', 'wine', 'pink', 'green', 'blue', 'navy', 'yellow', 'orange', 'cream', 'beige', 'white', 'black', 'peach', 'purple', 'lavender', 'grey', 'gray', 'brown', 'teal', 'turquoise', 'mustard', 'rust', 'mauve', 'lilac', 'olive', 'fuchsia', 'coral', 'blush']
FABRICS = ['silk blend', 'cotton blend', 'viscose crepe', 'cotton', 'rayon', 'silk', 'chanderi', 'muslin', 'viscose', 'georgette', 'brocade', 'taffeta']
OCCASIONS = {'festive': r'festiv\w*|diwali|eid|navratri|puja|pooja|festival|rakhi|holi', 'everyday': r'everyday|daily|casual|regular wear', 'office': r'office|work\s+wear|for\s+work|to\s+work|formal', 'wedding': r'wedding|sangeet|mehendi|mehndi|reception|engagement', 'party': r'party|parties|celebration'}
STYLES = {'A-Line': r'a[ -]?line', 'Anarkali': r'anarkali', 'Straight': r'straight', 'Flared': r'flared?', 'Angrakha': r'angrakha', 'Asymmetric': r'asymmetric'}
SIZE_ALIASES = {'XXL':'2XL', 'XXXL':'3XL', 'SMALL':'S', 'MEDIUM':'M', 'LARGE':'L', 'EXTRA LARGE':'XL'}

def fresh_profile():
    return {'budget': None, 'min_budget': None, 'size': None, 'colors': [], 'excluded_colors': [],
            'category': None, 'occasion': None, 'style': None, 'fabric': None, 'features': [],
            'excluded_features': [], 'excluded_fabrics': [], 'collection': None, 'sort': 'relevance'}

def normal(text):
    return re.sub(r'\s+', ' ', str(text or '').lower().replace('\u2019', "'")).strip()

def is_greeting(text):
    return bool(re.fullmatch(r'(?:hi+|hello+|hey+|namaste|good morning|good afternoon|good evening|start over|start again|restart|reset|new conversation|new chat)(?:\s+(?:there|kiaasa|again))?[\s!.?]*', normal(text)))

def canonical_color(text):
    text = normal(text)
    aliases = {'wine':'maroon', 'marron':'maroon', 'balck':'black', 'gray':'grey', 'off white':'white', 'navy':'blue', 'navy blue':'blue', 'powder blue':'blue', 'light blue':'blue', 'teal blue':'blue', 'rama green':'green', 'sage green':'green', 'pista green':'green', 'olive green':'green', 'olive':'green', 'mehandi':'green', 'fuchsia':'pink', 'blush':'pink', 'lilac':'purple', 'light brown':'brown'}
    return aliases.get(text, text)

def negated(text, start):
    return bool(re.search(r'\b(?:not|no|without|avoid|except|excluding)\s*(?:any\s+)?$', text[max(0,start-25):start]))

def amount(text):
    text = text.replace(',', '').replace(' ', '').lower()
    return float(text.rstrip('k')) * (1000 if text.endswith('k') else 1)

def update_profile(profile, message, awaiting=None):
    previous = copy.deepcopy(profile)
    text = normal(message)
    number = r'(\d[\d,]*(?:\.\d+)?\s*k?)'
    currency = r'(?:\u20b9|rs\.?|inr|rupees)?\s*'
    range_match = re.search(r'(?:between|from)\s*'+currency+number+r'\s*(?:and|to|-)\s*'+currency+number, text)
    if range_match:
        low,high=amount(range_match[1]),amount(range_match[2])
        profile['min_budget'],profile['budget']=min(low,high),max(low,high)
    else:
        maximum = re.search(r'(?:under|below|within|up to|upto|less than|not (?:above|over)|maximum|max|budget\s*(?:is|of|around|:)?|around)\s*'+currency+number, text)
        minimum = re.search(r'(?:above|over|more than|at least|minimum|min)\s*'+currency+number, text)
        if maximum:
            profile['budget'],profile['min_budget']=amount(maximum[1]),None
        elif minimum:
            profile['min_budget'],profile['budget']=amount(minimum[1]),None
        elif awaiting=='budget' and re.fullmatch(currency+number, text):
            profile['budget'],profile['min_budget']=amount(re.fullmatch(currency+number,text)[1]),None
        elif re.fullmatch(currency+number, text) and re.search(r'\u20b9|rs|inr|rupees',text):
            profile['budget'],profile['min_budget']=amount(re.fullmatch(currency+number,text)[1]),None
    if re.search(r'any budget|no budget|no price limit|remove (?:the )?budget',text):
        profile['budget'],profile['min_budget']=None,None
    positive_colors=[]
    occupied=[]
    for color in COLORS:
        for match in re.finditer(r'\b'+re.escape(color)+r'\b',text):
            if any(a<=match.start()<b for a,b in occupied):continue
            occupied.append(match.span())
            canonical=canonical_color(color)
            if negated(text,match.start()):
                if canonical not in profile['excluded_colors']:profile['excluded_colors'].append(canonical)
                profile['colors']=[c for c in profile['colors'] if c!=canonical]
            elif canonical not in positive_colors:positive_colors.append(canonical)
    if positive_colors:
        profile['colors']=positive_colors
        profile['excluded_colors']=[c for c in profile['excluded_colors'] if c not in positive_colors]
    if re.search(r'any colou?r|no colou?r preference|all colou?rs',text):
        profile['colors'],profile['excluded_colors']=[],[]
    size = re.search(r'\b(?:size\s*|in\s+)(xxxl|xxl|xxs|xs|3xl|2xl|xl|s|m|l|small|medium|large|extra large)\b',text)
    if not size:size=re.search(r'\b(xxxl|xxl|xxs|xs|3xl|2xl|xl)\b',text)
    if not size and re.fullmatch(r's|m|l|small|medium|large',text):size=re.fullmatch(r'(.*)',text)
    if size:profile['size']=SIZE_ALIASES.get(size[1].upper(),size[1].upper())
    if re.search(r'any size|remove (?:the )?size',text):profile['size']=None
    for fabric in FABRICS:
        match=re.search(r'\b'+re.escape(fabric)+r'\b',text)
        if match:
            if negated(text,match.start()):
                if fabric not in profile['excluded_fabrics']:profile['excluded_fabrics'].append(fabric)
                if normal(profile['fabric'])==fabric:profile['fabric']=None
            else:
                profile['fabric']=fabric.title()
                profile['excluded_fabrics']=[f for f in profile['excluded_fabrics'] if f!=fabric]
            break
    if re.search(r'any fabric|no fabric preference',text):profile['fabric']=None;profile['excluded_fabrics']=[]
    for style,pattern in STYLES.items():
        if re.search(r'\b(?:'+pattern+r')\b',text):profile['style']=style;break
    if re.search(r'any style|no style preference',text):profile['style']=None
    feature_rules={'embroidery':r'embroider\w*', 'print':r'print(?:ed|s)?', 'mirror':r'mirror(?: work)?', 'sequins':r'sequin\w*', 'hand work':r'hand[ -]?work', 'solid':r'solid|plain', 'sleeveless':r'sleeveless'}
    positives=[]
    for feature,pattern in feature_rules.items():
        match=re.search(r'\b(?:'+pattern+r')\b',text)
        if not match:continue
        if negated(text,match.start()):
            if feature not in profile['excluded_features']:profile['excluded_features'].append(feature)
            profile['features']=[f for f in profile['features'] if f!=feature]
        else:positives.append(feature)
    if positives:
        profile['features']=positives
        profile['excluded_features']=[f for f in profile['excluded_features'] if f not in positives]
    categories=[('Co-ord Set',r'co[ -]?ord(?:inate)?(?:s| sets?)?'),('Suit Set',r'suits?|salwar|three[ -]?piece|3[ -]?piece'),('Kurta Set',r'kurta\s+(?:pant\s+)?sets?|two[ -]?piece|2[ -]?piece'),('Tunic',r'tunics?'),('Kurti',r'kurtis?'),('Kurta',r'kurtas?'),('Dress',r'dress(?:es)?|gowns?'),('Bottom',r'pants?|palazzo|trousers?|leggings?')]
    for category,pattern in categories:
        if re.search(r'\b(?:'+pattern+r')\b',text):profile['category']=category;break
    if re.search(r'any (?:category|clothing type)|all (?:categories|clothing types)',text):profile['category']=None
    occasions=[]
    for occasion,pattern in OCCASIONS.items():
        for match in re.finditer(r'\b(?:'+pattern+r')\b',text):
            if not negated(text,match.start()):occasions.append((match.start(),occasion))
    if occasions:
        profile['occasion']=max(occasions)[1]
        desired='everyday' if profile['occasion'] in {'everyday','office'} else 'festive'
        if profile['collection'] in {'everyday','festive'} and profile['collection']!=desired:
            profile['collection']=None
    if re.search(r'any occasion|remove (?:the )?occasion',text):profile['occasion']=None;profile['collection']=None
    if re.search(r'new arrivals?|latest|newest',text):profile['collection']='new_arrivals'
    if re.search(r'cheapest|lowest price|low to high|affordable',text):profile['sort']='price'
    return previous!=profile

def valid_style(product):
    value=product.get('style')
    if value in STYLES:return value
    name=normal(product.get('name'))
    for style,pattern in STYLES.items():
        if re.search(r'\b(?:'+pattern+r')\b',name):return style
    return None

def category_matches(product, requested):
    source=normal(product.get('category'));name=normal(product.get('name'))
    if requested=='Suit Set':return source=='suit sets'
    if requested=='Kurta Set':return source in {'kurta sets','suit sets'}
    if requested=='Co-ord Set':return source=='co-ord sets'
    if requested in {'Kurta','Kurti','Tunic'}:
        return source in {'kurtas & tops','ethnic wear'} and bool(re.search(r'\b'+requested.lower()+r'\b',name))
    if requested=='Bottom':return source in {'bottom','bottoms','bottam'}
    return bool(re.search(r'\b'+re.escape(requested.lower())+r'\b',name))

def occasion_matches(product, requested):
    labels=' '.join(product.get('occasion') or [])+' '+str(product.get('name',''))
    if requested=='festive':return 'festive' in product.get('collections',[]) or bool(re.search(OCCASIONS['festive'],labels,re.I))
    if requested=='everyday':return 'everyday' in product.get('collections',[]) or bool(re.search(OCCASIONS['everyday'],labels,re.I))
    if requested=='office':return bool(re.search(r'office|work wear|formal',labels,re.I))
    # Wedding/party suitability must be stated in published product details.
    return bool(re.search(OCCASIONS.get(requested, re.escape(requested)), labels+' '+str(product.get('description','')),re.I))

def feature_matches(product, feature):
    specs=product.get('specifications') or {}
    evidence=' '.join([str(product.get('name','')), ' '.join(product.get('features') or []),str(specs.get('Pattern','')),str(specs.get('Sleeve Length','')),str(specs.get('Sleeve Type',''))]).lower()
    if feature=='embroidery':return 'embroider' in evidence
    if feature=='print':return 'print' in evidence
    if feature=='solid':return bool(re.search(r'\bsolid|\bplain',evidence))
    return feature in evidence

def matches(product, profile):
    if normal(product.get('stock')) in {'sold out','out of stock','unavailable'}:return False
    if re.search(r'\b(?:girls?|kids|boys?|children)\b',normal(product.get('name'))+' '+normal(product.get('category'))):return False
    price=product.get('price')
    if not isinstance(price,(int,float)) or price<=0:return False
    if profile.get('budget') is not None and price>profile['budget']:return False
    if profile.get('min_budget') is not None and price<profile['min_budget']:return False
    if profile.get('collection') and profile['collection'] not in product.get('collections',[]):return False
    if profile.get('category') and not category_matches(product,profile['category']):return False
    if profile.get('colors') and product.get('color_review_required'):
        return False
    color=canonical_color(product.get('color'))
    if profile.get('colors') and color not in profile['colors']:return False
    if color in profile.get('excluded_colors',[]):return False
    if profile.get('size'):
        sizes={SIZE_ALIASES.get(str(s).upper(),str(s).upper()) for s in product.get('sizes',[])}
        if profile['size'] not in sizes:return False
    if profile.get('occasion') and not occasion_matches(product,profile['occasion']):return False
    fabric=normal(product.get('fabric'))
    if profile.get('fabric') and normal(profile['fabric']) not in fabric:return False
    if any(f in fabric for f in profile.get('excluded_fabrics',[])):return False
    if profile.get('style') and valid_style(product)!=profile['style']:return False
    if any(not feature_matches(product,f) for f in profile.get('features',[])):return False
    if any(feature_matches(product,f) for f in profile.get('excluded_features',[])):return False
    return True

def search(products, profile, limit=5, offset=0):
    eligible=[p for p in products if matches(p,profile)]
    eligible.sort(key=(lambda p:(p['price'],p.get('latest_collection_rank',10000))) if profile.get('sort')=='price' else (lambda p:p.get('latest_collection_rank',10000)))
    selected=eligible[offset:offset+limit] if limit is not None else eligible[offset:]
    return [decorate(p,profile) for p in selected],len(eligible)

def money(value):return '\u20b9'+format(value,',.0f')

def preference_summary(profile):
    bits=[]
    occasion=profile.get('occasion')
    if occasion:bits.append({'everyday':'everyday wear','office':'work wear'}.get(occasion,occasion+' wear'))
    elif profile.get('collection'):bits.append({'festive':'festive wear','everyday':'everyday wear','new_arrivals':'newest-season styles'}[profile['collection']])
    if profile.get('category'):bits.append(profile['category'].lower())
    if profile.get('colors'):bits.append(' or '.join(profile['colors']))
    if profile.get('min_budget') is not None and profile.get('budget') is not None:bits.append(money(profile['min_budget'])+'–'+money(profile['budget']))
    elif profile.get('budget') is not None:bits.append('up to '+money(profile['budget']))
    elif profile.get('min_budget') is not None:bits.append('from '+money(profile['min_budget']))
    for key in ['fabric','style']:
        if profile.get(key):bits.append(profile[key].lower())
    if profile.get('size'):bits.append('size '+profile['size'])
    bits.extend(profile.get('features',[]))
    for field,label in [('excluded_colors','without '),('excluded_features','without '),('excluded_fabrics','without ')]:
        bits.extend(label+v for v in profile.get(field,[]))
    return ' · '.join(bits)

def decorate(product,profile):
    card=dict(product)
    if product.get('color_review_required'):
        card['color']='Needs confirmation (website lists '+str(product.get('color') or 'unknown')+')'
    image=str(product.get('image_url') or product.get('image') or '')
    if re.search(r'(?:/kiaasa\.png|placeholder|no[-_]?image)(?:\?|$)',image,re.I):
        card['image_url']=None
        card['image']=None
        card['image_unavailable']=True
    card['display_name']=product['name'].split('|')[0].strip()
    card['style']=valid_style(product)
    reasons=[]
    if profile.get('occasion'):reasons.append({'everyday':'Everyday style','office':'Work-wear style'}.get(profile['occasion'],profile['occasion'].title()+' style'))
    elif profile.get('collection'):reasons.append({'new_arrivals':'Newest listed season','festive':'Festive style','everyday':'Everyday style'}[profile['collection']])
    if profile.get('budget') is not None:reasons.append('Within your '+money(profile['budget'])+' budget')
    if profile.get('colors'):reasons.append(str(product.get('color'))+' colour')
    if profile.get('fabric'):reasons.append(str(product.get('fabric'))+' fabric')
    if profile.get('size'):reasons.append('Size '+profile['size']+' listed; confirm availability')
    card['match_reasons']=reasons
    return card

def reply(text, profile, intent='assistant', products=None, **extras):
    products=products or []
    return {'reply':text,'intent':intent,'profile':profile,'products':products,'matches':len(products),'preference_summary':preference_summary(profile),**extras}

def service_answer(message,profile):
    text=normal(message)
    if re.search(r'\b(?:stores?|shops? near|location|nearest|address|opening hours)\b',text):
        return reply('Use Find a Store to search your city or pincode, or allow location access to see nearby stores and their published hours.',profile,'store_locator',links=[{'label':'Find a Store','url':'stores.html'}])
    policies=[(r'\b(?:return|returns|exchange|refund)\b','For a return, exchange or refund, contact Kiaasa customer care with your order number. Eligibility depends on the published policy and your order.', 'Refund and returns policy','https://www.kiaasa.in/refund'),
              (r'\b(?:cancel|cancellation)\b','To request an order cancellation, contact Kiaasa customer care with your order number. I cannot cancel orders in this chat.','Contact customer care','https://www.kiaasa.in/contact-us'),
              (r'\b(?:shipping|delivery|deliver|pincode|pin code|international)\b','Delivery availability, charges and timing depend on your address and checkout. For an existing shipment, use Track My Order.','Shipping policy','https://www.kiaasa.in/shipping-policy'),
              (r'\b(?:payment|payments|cod|cash on delivery|coupon|discount code|promo code)\b','Check the options and offers shown at Kiaasa checkout. I cannot confirm a payment or apply a coupon here. For a payment issue, contact customer care with your order number.','Kiaasa FAQ','https://www.kiaasa.in/faq'),
              (r'\b(?:contact|customer care|support|human|agent|complaint)\b','You can contact Kiaasa customer care at customercare@kiaasaretail.com for account or order assistance.','Contact customer care','https://www.kiaasa.in/contact-us')]
    for pattern,answer,label,url in policies:
        if re.search(pattern,text):return reply(answer,profile,'customer_service',links=[{'label':label,'url':url}])
    if re.search(r'size chart|size guide|measure|measurements|which size|what size|sizing',text):
        return reply("Use the size chart on the specific product page—measurements can vary between styles. If you know your size, tell me (for example, size XL) and I'll filter the listed sizes. Final availability is confirmed on the product page.",profile,'size_help')
    if re.fullmatch(r'(?:thanks?|thank you|thankyou|ok(?:ay)?|great|nice)[!. ]*',text):
        return reply("You're welcome! Tell me if you'd like another colour, a different budget, or more styles.",profile)
    if re.search(r'who are you|what can you do|how (?:do|can) i (?:use|shop)',text) or text in {'help','help me'}:
        return reply('I can help you find Kiaasa styles by occasion, budget, colour, fabric and size, explain a product, find a store, or track an order. What are you shopping for?',profile,suggestions=['Festive under 1500','Everyday under 2000','Track my order'])
    return None

def shopping_response(products,profile,context,message,original_message=None):
    service=service_answer(message,profile)
    if service:return service
    text=normal(message)
    # Product follow-ups use only the cards in the most recent result.
    detail_request=bool(re.search(r'tell me (?:more|about)|details|fabric of|sizes? (?:of|for|available)|what material|available in|this product|that product|first one|second one|third one',text))
    if detail_request and context.get('last_products'):
        index=0
        for word,value in [('first',0),('second',1),('third',2),('fourth',3),('fifth',4)]:
            if re.search(r'\b'+word+r'\b',text):index=value
        if index>=len(context['last_products']):return reply('Please choose one of the products shown above.',profile)
        product=context['last_products'][index]
        changed=update_profile(profile,message,context.get('awaiting'))
        if original_message is not None:
            changed=update_profile(profile,original_message,context.get('awaiting')) or changed
        if changed and not matches(product,profile):
            return recommendation(products,profile,context)
        details=product['display_name']+'\nPrice: '+money(product['price'])
        for key,label in [('color','Colour'),('fabric','Fabric'),('style','Style')]:
            if product.get(key):details+='\n'+label+': '+str(product[key])
        if product.get('sizes'):details+='\nListed sizes: '+', '.join(product['sizes'])
        details+='\nPlease confirm current price and size availability on the product page.'
        return reply(details,profile,'product_details',products=[product])
    changed=update_profile(profile,message,context.get('awaiting'))
    if original_message is not None:
        changed=update_profile(profile,original_message,context.get('awaiting')) or changed
    more=bool(re.search(r'\b(?:show|see|view) more\b|more (?:options|styles|products)|other (?:options|styles)',text))
    shopping_words=bool(re.search(r'\b(?:shop|shopping|show|browse|recommend|suggest|looking|want|need|wear|outfit|something|anything|cheapest)\b',text))
    if not changed and not more and not shopping_words:
        return reply("I can help with Kiaasa shopping, sizes, stores, order tracking and customer-care questions. For a style search, tell me an occasion or preference—for example, festive wear under 1500.",profile,suggestions=['Festive under 1500','Everyday under 2000','Find a Store'])
    meaningful=any(profile.get(k) for k in ['occasion','collection','category','colors','fabric','style','features','size'])
    if not meaningful:
        context['awaiting']='occasion'
        budget='Your budget is '+preference_summary(profile)+'. ' if profile.get('budget') is not None else ''
        return reply(budget+'What occasion are you shopping for—festive, everyday, or work wear?',profile,'clarification',suggestions=['Festive wear','Everyday styles','Work wear'])
    return recommendation(products,profile,context,more=more and not changed)

def recommendation(products,profile,context,more=False):
    offset=context.get('offset',0)+5 if more else 0
    selected,total=search(products,profile,offset=offset)
    summary=preference_summary(profile)
    if total and not selected:
        return reply('You have seen all '+str(total)+' matching styles. Would you like to change a colour or budget?',profile,'shopping',total_matches=total)
    if not selected:
        context['offset']=0;context['last_products']=[];context['awaiting']=None
        alternatives=[]
        for key,label in [('budget','increase the budget'),('size','try another size'),('colors','try another colour'),('fabric','try another fabric'),('style','try another style'),('features','try another design'),('collection','browse the wider catalogue')]:
            if not profile.get(key):continue
            relaxed=copy.deepcopy(profile);relaxed[key]=[] if isinstance(profile[key],list) else None
            _,count=search(products,relaxed)
            if count:alternatives.append(label);break
        next_step='Would you like to '+alternatives[0]+'?' if alternatives else 'Would you like to change the occasion or another preference?'
        return reply("I couldn't find an exact match for "+summary+'. '+next_step+' I have kept your preferences unchanged.',profile,'shopping',total_matches=0)
    context['offset']=offset;context['last_products']=selected
    question=''
    if profile.get('budget') is None and profile.get('min_budget') is None:
        context['awaiting']='budget';question=' What budget would you like to stay within?'
    else:context['awaiting']=None
    return reply('Here are '+str(len(selected))+' of '+str(total)+' matching styles for '+summary+'.'+question,profile,'shopping',products=selected,total_matches=total,suggestions=['Show more'] if offset+len(selected)<total else [])
