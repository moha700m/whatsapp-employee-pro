"""ALL WhatsApp Web / ChatGPT selectors in one place. WhatsApp changes its DOM often:
update here only. Each entry is a list tried in order (aria/role/data-testid first)."""

WA_URL = "https://web.whatsapp.com/"
WA = {
    "ready": ["#pane-side", "div#side", "[data-testid='chat-list']", "[aria-label='Chat list']", "[aria-label='قائمة الدردشات']", "div[role='grid']"],
    # extra states (text selectors are matched case-insensitively by Playwright)
    "qr_container": ["canvas[aria-label*='QR' i]", "div[data-ref]", "div[data-testid='qrcode']"],
    "use_here": ["button:has-text('Use here')", "button:has-text('استخدام هنا')", "div[role='button']:has-text('Use here')",
                 "div[role='button']:has-text('استخدام هنا')"],
    "conflict": ["text=WhatsApp is open in another window", "text=واتساب مفتوح في نافذة أخرى", "text=is open in another window"],
    "phone_offline": ["text=Phone not connected", "text=الهاتف غير متصل", "[data-testid='alert-phone']",
                      "span[data-icon='alert-phone']"],
    "loading_bar": ["progress", "[data-testid='startup']", "div[data-testid='intro-md-beta-logo-dark']"],
    "profile_button": ["header [data-testid='default-user']", "header img[draggable='false']", "#app header [role='button'] img"],
    "profile_name": ["[data-testid='profile-name']", "span[data-testid='me-name']"],
    "qr": ["canvas[aria-label*='Scan']", "canvas[aria-label*='QR']", "[data-ref] canvas", "div[data-testid='qrcode'] canvas"],
    "chat_row": ["div[data-testid='cell-frame-container']", "#pane-side div[role='listitem']", "#pane-side div[role='row']", "#pane-side div[role='gridcell']",
                 "div[aria-label='Chat list'] > div > div", "div[aria-label='قائمة الدردشات'] > div > div"],
    "unread_badge": ["span[data-testid='icon-unread']", "span[aria-label*='unread' i]", "span[aria-label*='غير مقروء']", "span[aria-label*='غير مقروءة']",
                     "span[aria-label*='رسالة غير']", "span[aria-label*='رسائل غير']", "span[data-testid='icon-unread-count']",
                     "div[aria-label*='unread' i] span"],
    "row_title": ["span[dir='auto'][title]", "span[title]", "div[role='gridcell'] span[dir='auto']"],
    "row_last_msg": ["div[role='gridcell'] + div span[dir='ltr']", "span[dir='ltr'][title]", "div > span[title]:not([dir='auto'])"],
    "group_hint": ["[data-icon='default-group']", "[data-testid='default-group']", "[data-icon='group']"],
    "message": ["#main div[data-id]", "div[role='application'] div[data-id]", "#main div.message-in, #main div.message-out"],
    "message_text": ["span.selectable-text", "span[dir] span", "div.copyable-text span"],
    "message_meta": ["div.copyable-text"],   # data-pre-plain-text="[time, date] Sender: "
    "compose": ["div#main footer div[contenteditable='true']", "#main footer div[contenteditable='true'][data-tab='10']", "footer div[contenteditable='true'][role='textbox']",
                "div[aria-label='Type a message'][contenteditable='true']", "div[aria-label='اكتب رسالة'][contenteditable='true']", "div[aria-label='Type a message']",
                "div[aria-label='اكتب رسالة']", "footer div[contenteditable='true']"],
    "send_button": ["button[aria-label='Send']", "button[aria-label='إرسال']", "span[data-icon='wds-ic-send-filled']", "span[data-icon='send']",
                    "[data-testid='send']"],
    "header_title": ["#main header span[dir='auto'][title]", "#main header span[title]", "#main header span[dir='auto']",
                     "#main header div[role='button'] span"],
    "header_subtitle": ["#main header span[title]:not([dir])", "#main header div[title]"],
    # media detection (flagged in the UI for manual handling — nothing is downloaded or transcribed)
    "media_voice": ["span[data-icon='audio-play']", "span[data-icon='ptt-status']", "button[aria-label*='voice' i]", "button[aria-label*='صوت']", "audio"],
    "media_image": ["img[src^='blob:']", "div[aria-label*='Image' i]", "div[aria-label*='صورة']", "span[data-icon='media-play']"],
    "media_video": ["span[data-icon='media-play']", "video", "div[aria-label*='Video' i]"],
    "media_document": ["span[data-icon='audio-file']", "span[data-icon*='document']", "div[aria-label*='Document' i]", "div[aria-label*='مستند']"],
    "media_sticker": ["img[alt*='sticker' i]", "div[aria-label*='Sticker' i]", "div[aria-label*='ملصق']"],
}

# Keys that must resolve on a connected page; checked by the startup self-test (whatsapp_web.self_test)
SELF_TEST_KEYS = ["ready", "chat_row", "row_title"]
SELF_TEST_CHAT_KEYS = ["message", "compose", "header_title"]

CHATGPT_URL = "https://chatgpt.com/"
GPT = {
    "prompt": ["#prompt-textarea", "div[contenteditable='true'][id='prompt-textarea']", "textarea[data-testid='prompt-textarea']"],
    "send": ["button[data-testid='send-button']", "button[aria-label='Send prompt']", "button[aria-label*='Send']"],
    "stop": ["button[data-testid='stop-button']", "button[aria-label*='Stop']"],
    "assistant_msg": ["div[data-message-author-role='assistant']"],
    "login_hint": ["button[data-testid='login-button']", "a[href*='auth/login']"],
}
