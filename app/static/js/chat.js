/**
 * MultiTool AI — Chat Interaction Module
 * Handles all chat CRUD, messaging, file uploads, and UI updates.
 */
(function () {
    'use strict';

    /* ===== State ===== */
    var activeChatId = null;
    var activeChatMeta = null;
    var isLoading = false;
    var attachedFiles = [];

    /* ===== DOM References (lazy-initialized) ===== */
    var DOM = {};

    function cacheDom() {
        DOM.messageArea = document.getElementById('message-area');
        DOM.messageList = document.getElementById('message-list');
        DOM.welcomeScreen = document.getElementById('welcome-screen');
        DOM.emptyState = document.getElementById('empty-state');
        DOM.chatHeader = document.getElementById('chat-header-content');
        DOM.chatTitle = document.getElementById('chat-header-title');
        DOM.chatActions = document.getElementById('chat-header-actions');
        DOM.composer = document.getElementById('composer');
        DOM.messageInput = document.getElementById('message-input');
        DOM.sendBtn = document.getElementById('btn-send');
        DOM.fileInput = document.getElementById('file-input');
        DOM.attachBtn = document.getElementById('btn-attach');
        DOM.attachmentsPreview = document.getElementById('composer-attachments');
        DOM.chatList = document.getElementById('chat-list');
        DOM.searchInput = document.getElementById('chat-search');
        DOM.newChatBtn = document.getElementById('btn-new-chat');
        DOM.newChatForm = document.getElementById('new-chat-form');
        DOM.newChatModal = document.getElementById('newChatModal');
        DOM.chatSettingsModal = document.getElementById('chatSettingsModal');
        DOM.chatSettingsForm = document.getElementById('chat-settings-form');
        DOM.chatSettingsTitle = document.getElementById('chat-settings-title');
        DOM.chatSettingsInstruction = document.getElementById('chat-settings-instruction');
        DOM.chatSettingsBtn = document.getElementById('btn-chat-settings');
        DOM.deleteChatModal = document.getElementById('deleteChatModal');
        DOM.confirmDeleteBtn = document.getElementById('btn-confirm-delete');
    }

    /* ===== Load Chat ===== */
    function loadChat(chatId) {
        if (isLoading || !chatId) return;

        activeChatId = chatId;
        isLoading = true;

        /* Update sidebar active state */
        updateActiveSidebarItem(chatId);

        fetch('/chat/' + chatId, {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
        })
        .then(function (res) {
            if (!res.ok) throw new Error('Failed to load chat');
            return res.json();
        })
        .then(function (data) {
            var chat = data.chat;
            var messages = data.messages || [];
            activeChatMeta = {
                id: chat.id,
                title: chat.title || 'Untitled',
                system_instruction: chat.system_instruction || ''
            };

            /* Update header */
            showChatHeader(chat.title, chatId);

            /* Render messages */
            showMessageList();
            DOM.messageList.innerHTML = '';

            if (messages.length === 0) {
                showEmptyState();
            } else {
                hideEmptyState();
                messages.forEach(function (msg) {
                    var el = createMessageElement(msg, msg.role, messages);
                    DOM.messageList.appendChild(el);
                });
                scrollToBottom();
            }

            /* Show composer */
            DOM.composer.style.display = '';

            /* Close sidebar on mobile */
            if (window.innerWidth <= 768) {
                window.closeSidebar();
            }
        })
        .catch(function (err) {
            console.error('loadChat error:', err);
            window.showToast('Failed to load chat', 'error');
        })
        .finally(function () {
            isLoading = false;
        });
    }

    /* ===== Send Message ===== */
    function sendMessage() {
        if (isLoading || !activeChatId) return;

        var text = DOM.messageInput.value.trim();
        if (!text && attachedFiles.length === 0) return;

        isLoading = true;
        updateSendButtonState();

        /* Build FormData */
        var formData = new FormData();
        formData.append('message', text);
        attachedFiles.forEach(function (f) {
            formData.append('files', f);
        });

        /* Show user message immediately (optimistic) */
        var userMsg = {
            id: 'temp-' + Date.now(),
            role: 'user',
            content: text,
            timestamp: new Date().toISOString(),
            attachments: attachedFiles.map(function (f) {
                return { original_filename: f.name, mime_type: f.type, size: f.size };
            })
        };

        hideEmptyState();
        hideWelcomeScreen();
        var userEl = createMessageElement(userMsg, 'user', []);
        DOM.messageList.appendChild(userEl);
        scrollToBottom();

        /* Clear composer */
        DOM.messageInput.value = '';
        DOM.messageInput.style.height = 'auto';
        attachedFiles = [];
        updateFilePreview();
        updateSendButtonState();

        /* Show typing indicator */
        showTypingIndicator();

        fetch('/chat/' + activeChatId + '/send', {
            method: 'POST',
            headers: { 'X-CSRFToken': window.getCSRFToken() },
            body: formData
        })
        .then(function (res) {
            if (!res.ok) throw new Error('Failed to send message');
            return res.json();
        })
        .then(function (data) {
            hideTypingIndicator();

            /* Replace temp user message with real one */
            var tempEl = DOM.messageList.querySelector('[data-msg-id="' + userMsg.id + '"]');
            if (tempEl && data.user_message) {
                tempEl.setAttribute('data-msg-id', data.user_message.id);
            }

            /* Show assistant message */
            if (data.assistant_message) {
                var assistantEl = createMessageElement(data.assistant_message, 'assistant', []);
                DOM.messageList.appendChild(assistantEl);
                updateRegenerateButtons();
                scrollToBottom();
            }
        })
        .catch(function (err) {
            hideTypingIndicator();
            console.error('sendMessage error:', err);
            window.showToast('Failed to send message. Please try again.', 'error');
        })
        .finally(function () {
            isLoading = false;
            updateSendButtonState();
            DOM.messageInput.focus();
        });
    }

    /* ===== Create Chat ===== */
    function createChat() {
        var titleInput = document.getElementById('new-chat-title');
        var instructionInput = document.getElementById('new-chat-instruction');

        var title = titleInput.value.trim();
        var instruction = instructionInput.value.trim();

        if (!title) {
            titleInput.focus();
            return;
        }

        fetch('/chat/new', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': window.getCSRFToken()
            },
            body: JSON.stringify({
                title: title,
                system_instruction: instruction
            })
        })
        .then(function (res) {
            if (!res.ok) throw new Error('Failed to create chat');
            return res.json();
        })
        .then(function (data) {
            /* Close modal */
            var modal = bootstrap.Modal.getInstance(DOM.newChatModal);
            if (modal) modal.hide();

            /* Reset form */
            titleInput.value = '';
            instructionInput.value = '';

            /* Add to sidebar */
            var chatItem = createChatListItem({
                id: data.id,
                title: data.title,
                updated_at: data.created_at
            });
            DOM.chatList.insertBefore(chatItem, DOM.chatList.firstChild);

            /* Load the new chat */
            loadChat(data.id);

            window.showToast('Chat created!', 'success');
        })
        .catch(function (err) {
            console.error('createChat error:', err);
            window.showToast('Failed to create chat', 'error');
        });
    }

    /* ===== Rename Chat ===== */
    function renameChat(chatId, newTitle) {
        if (!newTitle || !chatId) return;

        fetch('/chat/' + chatId + '/rename', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': window.getCSRFToken()
            },
            body: JSON.stringify({ title: newTitle })
        })
        .then(function (res) {
            if (!res.ok) throw new Error('Rename failed');
            return res.json();
        })
        .then(function (data) {
            if (data.success) {
                if (activeChatMeta && String(activeChatMeta.id) === String(chatId)) {
                    activeChatMeta.title = data.title;
                }

                if (DOM.chatTitle && String(activeChatId) === String(chatId)) {
                    DOM.chatTitle.textContent = data.title;
                }

                /* Update sidebar item */
                var item = DOM.chatList.querySelector('[data-chat-id="' + chatId + '"]');
                if (item) {
                    var titleEl = item.querySelector('.chat-list-item-title');
                    if (titleEl) titleEl.textContent = data.title;
                }
                window.showToast('Chat renamed', 'success');
            }
        })
        .catch(function (err) {
            console.error('renameChat error:', err);
            window.showToast('Failed to rename chat', 'error');
        });
    }

    function updateChatSettings(chatId, title, systemInstruction) {
        return fetch('/chat/' + chatId + '/settings', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': window.getCSRFToken()
            },
            body: JSON.stringify({
                title: title,
                system_instruction: systemInstruction
            })
        })
        .then(function (res) {
            if (!res.ok) throw new Error('Update failed');
            return res.json();
        })
        .then(function (data) {
            if (!data.success || !data.chat) {
                throw new Error('Invalid settings response');
            }

            activeChatMeta = {
                id: data.chat.id,
                title: data.chat.title || 'Untitled',
                system_instruction: data.chat.system_instruction || ''
            };

            showChatHeader(activeChatMeta.title, activeChatMeta.id);

            var item = DOM.chatList.querySelector('[data-chat-id="' + chatId + '"]');
            if (item) {
                var titleEl = item.querySelector('.chat-list-item-title');
                if (titleEl) titleEl.textContent = activeChatMeta.title;
            }

            return data.chat;
        });
    }

    function openChatSettingsModal() {
        if (!activeChatId || !activeChatMeta || !DOM.chatSettingsModal) return;

        DOM.chatSettingsTitle.value = activeChatMeta.title || '';
        DOM.chatSettingsInstruction.value = activeChatMeta.system_instruction || '';

        var modal = new bootstrap.Modal(DOM.chatSettingsModal);
        modal.show();
    }

    /* ===== Delete Chat ===== */
    var pendingDeleteId = null;

    function promptDeleteChat(chatId) {
        pendingDeleteId = chatId;
        var modal = new bootstrap.Modal(DOM.deleteChatModal);
        modal.show();
    }

    function confirmDeleteChat() {
        if (!pendingDeleteId) return;

        var chatId = pendingDeleteId;
        pendingDeleteId = null;

        fetch('/chat/' + chatId, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': window.getCSRFToken() }
        })
        .then(function (res) {
            if (!res.ok) throw new Error('Delete failed');
            return res.json();
        })
        .then(function (data) {
            if (data.success) {
                /* Close modal */
                var modal = bootstrap.Modal.getInstance(DOM.deleteChatModal);
                if (modal) modal.hide();

                /* Remove from sidebar */
                var item = DOM.chatList.querySelector('[data-chat-id="' + chatId + '"]');
                if (item) item.remove();

                /* Show welcome if deleted active chat */
                if (activeChatId === chatId) {
                    activeChatId = null;
                    activeChatMeta = null;
                    showWelcomeScreen();
                    hideChatHeader();
                    DOM.composer.style.display = 'none';
                }

                window.showToast('Chat deleted', 'success');
            }
        })
        .catch(function (err) {
            console.error('deleteChat error:', err);
            window.showToast('Failed to delete chat', 'error');
        });
    }

    /* ===== Regenerate Response ===== */
    function regenerateResponse() {
        if (isLoading || !activeChatId) return;

        isLoading = true;

        /* Remove last assistant message */
        var allMessages = DOM.messageList.querySelectorAll('.message.assistant');
        var lastAssistant = allMessages[allMessages.length - 1];
        if (lastAssistant) lastAssistant.remove();

        showTypingIndicator();

        fetch('/chat/' + activeChatId + '/regenerate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': window.getCSRFToken()
            }
        })
        .then(function (res) {
            if (!res.ok) throw new Error('Regenerate failed');
            return res.json();
        })
        .then(function (data) {
            hideTypingIndicator();

            if (data.assistant_message) {
                var el = createMessageElement(data.assistant_message, 'assistant', []);
                DOM.messageList.appendChild(el);
                updateRegenerateButtons();
                scrollToBottom();
            }
        })
        .catch(function (err) {
            hideTypingIndicator();
            console.error('regenerateResponse error:', err);
            window.showToast('Failed to regenerate response', 'error');
        })
        .finally(function () {
            isLoading = false;
        });
    }

    /* ===== Copy to Clipboard ===== */
    function copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(function () {
            window.showToast('Copied to clipboard', 'success');
        }).catch(function () {
            /* Fallback */
            var ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            window.showToast('Copied to clipboard', 'success');
        });
    }

    /* ===== Search Chats ===== */
    var searchChats = window.debounce(function (query) {
        if (!query || query.trim() === '') {
            /* Reload full list */
            fetchAllChats();
            return;
        }

        fetch('/api/chats/search?q=' + encodeURIComponent(query.trim()), {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
        })
        .then(function (res) {
            if (!res.ok) throw new Error('Search failed');
            return res.json();
        })
        .then(function (data) {
            renderChatList(data.chats || []);
        })
        .catch(function (err) {
            console.error('searchChats error:', err);
        });
    }, 300);

    function fetchAllChats() {
        fetch('/api/chats', {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
        })
        .then(function (res) {
            if (!res.ok) throw new Error('Failed to fetch chats');
            return res.json();
        })
        .then(function (data) {
            renderChatList(data.chats || []);
        })
        .catch(function (err) {
            console.error('fetchAllChats error:', err);
        });
    }

    /* ===== DOM Helpers ===== */

    /**
     * Create a message element for the message area.
     */
    function createMessageElement(msg, role, allMessages) {
        var wrapper = document.createElement('div');
        wrapper.className = 'message ' + role;
        wrapper.setAttribute('data-msg-id', msg.id);

        /* Avatar */
        var avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = role === 'user' ? '👤' : '🤖';

        /* Bubble */
        var bubble = document.createElement('div');
        bubble.className = 'message-bubble';

        /* Content */
        var content = document.createElement('div');
        content.className = 'message-content';

        if (role === 'assistant') {
            /* Render markdown for assistant messages */
            var rawContent = msg.rendered_content || msg.content || '';
            if (msg.rendered_content) {
                /* Server already rendered — sanitize and use */
                content.innerHTML = DOMPurify.sanitize(rawContent, {
                    ALLOWED_TAGS: [
                        'h1','h2','h3','h4','h5','h6','p','br','hr',
                        'strong','b','em','i','u','s','del','ins','mark','sub','sup',
                        'ul','ol','li','blockquote','pre','code',
                        'a','img','table','thead','tbody','tfoot','tr','th','td',
                        'div','span','details','summary','dl','dt','dd','button'
                    ],
                    ALLOWED_ATTR: [
                        'href','target','rel','title','src','alt','width','height',
                        'class','id','style','colspan','rowspan','data-code','onclick','open'
                    ],
                    ALLOW_DATA_ATTR: true
                });
            } else {
                content.innerHTML = window.renderMarkdown(msg.content || '');
            }
        } else {
            /* User messages: plain text with line breaks */
            content.textContent = msg.content || '';
            content.style.whiteSpace = 'pre-wrap';
        }

        bubble.appendChild(content);

        /* Attachments (for user messages) */
        if (msg.attachments && msg.attachments.length > 0) {
            var attachDiv = document.createElement('div');
            attachDiv.className = 'message-attachments';
            msg.attachments.forEach(function (att) {
                var badge = document.createElement('span');
                badge.className = 'attachment-badge';
                badge.innerHTML = '📎 <span>' + window.escapeHtml(att.original_filename) + '</span>';
                attachDiv.appendChild(badge);
            });
            bubble.appendChild(attachDiv);
        }

        /* Timestamp */
        var timestamp = document.createElement('span');
        timestamp.className = 'message-timestamp';
        timestamp.textContent = window.formatTimestamp(msg.timestamp);

        bubble.appendChild(timestamp);

        /* Actions (for assistant messages) */
        if (role === 'assistant') {
            var actions = document.createElement('div');
            actions.className = 'message-actions';

            /* Copy button */
            var copyBtn = document.createElement('button');
            copyBtn.className = 'btn-msg-action';
            copyBtn.innerHTML = '📋 Copy';
            copyBtn.addEventListener('click', function () {
                copyToClipboard(msg.content || '');
            });
            actions.appendChild(copyBtn);

            /* Export dropdown */
            var exportDiv = document.createElement('div');
            exportDiv.className = 'export-dropdown';

            var exportBtn = document.createElement('button');
            exportBtn.className = 'btn-msg-action';
            exportBtn.innerHTML = '⬇ Export';
            exportBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                var menu = exportDiv.querySelector('.export-dropdown-menu');
                menu.classList.toggle('show');
            });

            var exportMenu = document.createElement('div');
            exportMenu.className = 'export-dropdown-menu';

            ['md', 'pdf', 'docx'].forEach(function (fmt) {
                var item = document.createElement('a');
                item.className = 'export-dropdown-item';
                item.href = '/export/' + msg.id + '/' + fmt;
                item.textContent = fmt.toUpperCase();
                item.download = '';
                exportMenu.appendChild(item);
            });

            exportDiv.appendChild(exportBtn);
            exportDiv.appendChild(exportMenu);
            actions.appendChild(exportDiv);

            /* Regenerate button (only for last assistant message) */
            var regenBtn = document.createElement('button');
            regenBtn.className = 'btn-msg-action btn-regenerate';
            regenBtn.innerHTML = '🔄 Regenerate';
            regenBtn.addEventListener('click', function () {
                regenerateResponse();
            });
            actions.appendChild(regenBtn);

            bubble.appendChild(actions);
        }

        wrapper.appendChild(avatar);
        wrapper.appendChild(bubble);

        return wrapper;
    }

    /**
     * Update regenerate buttons — only show on last assistant message.
     */
    function updateRegenerateButtons() {
        var allRegenBtns = DOM.messageList.querySelectorAll('.btn-regenerate');
        allRegenBtns.forEach(function (btn) {
            btn.style.display = 'none';
        });

        var assistantMsgs = DOM.messageList.querySelectorAll('.message.assistant');
        if (assistantMsgs.length > 0) {
            var lastMsg = assistantMsgs[assistantMsgs.length - 1];
            var regenBtn = lastMsg.querySelector('.btn-regenerate');
            if (regenBtn) regenBtn.style.display = '';
        }
    }

    /**
     * Create a sidebar chat list item.
     */
    function createChatListItem(chat) {
        var item = document.createElement('div');
        item.className = 'chat-list-item';
        if (chat.id === activeChatId) item.classList.add('active');
        item.setAttribute('data-chat-id', chat.id);

        item.innerHTML =
            '<div class="chat-list-item-icon">💬</div>' +
            '<div class="chat-list-item-content">' +
                '<div class="chat-list-item-title">' + window.escapeHtml(chat.title || 'Untitled') + '</div>' +
                '<div class="chat-list-item-time">' + window.formatTimestamp(chat.updated_at) + '</div>' +
            '</div>';

        item.addEventListener('click', function () {
            loadChat(chat.id);
        });

        return item;
    }

    /**
     * Render the full chat list from an array.
     */
    function renderChatList(chats) {
        DOM.chatList.innerHTML = '';
        if (chats.length === 0) {
            DOM.chatList.innerHTML = '<div class="chat-list-empty">No chats found</div>';
            return;
        }
        chats.forEach(function (chat) {
            DOM.chatList.appendChild(createChatListItem(chat));
        });
    }

    /**
     * Update the active state in the sidebar.
     */
    function updateActiveSidebarItem(chatId) {
        DOM.chatList.querySelectorAll('.chat-list-item').forEach(function (el) {
            el.classList.remove('active');
        });
        var active = DOM.chatList.querySelector('[data-chat-id="' + chatId + '"]');
        if (active) active.classList.add('active');
    }

    /* ===== UI State Helpers ===== */
    function showWelcomeScreen() {
        if (DOM.welcomeScreen) DOM.welcomeScreen.style.display = '';
        if (DOM.emptyState) DOM.emptyState.style.display = 'none';
        if (DOM.messageList) DOM.messageList.style.display = 'none';
    }

    function hideWelcomeScreen() {
        if (DOM.welcomeScreen) DOM.welcomeScreen.style.display = 'none';
    }

    function showEmptyState() {
        if (DOM.emptyState) DOM.emptyState.style.display = '';
        if (DOM.messageList) DOM.messageList.style.display = 'none';
        hideWelcomeScreen();
    }

    function hideEmptyState() {
        if (DOM.emptyState) DOM.emptyState.style.display = 'none';
        if (DOM.messageList) DOM.messageList.style.display = '';
    }

    function showMessageList() {
        hideWelcomeScreen();
        if (DOM.messageList) DOM.messageList.style.display = '';
    }

    function showChatHeader(title, chatId) {
        if (DOM.chatTitle) {
            DOM.chatTitle.textContent = title;
            DOM.chatTitle.setAttribute('data-original-title', title || '');
            DOM.chatTitle.setAttribute('data-chat-id', chatId);
            DOM.chatTitle.style.display = '';
        }
        if (DOM.chatActions) DOM.chatActions.style.display = '';
    }

    function hideChatHeader() {
        if (DOM.chatTitle) DOM.chatTitle.style.display = 'none';
        if (DOM.chatActions) DOM.chatActions.style.display = 'none';
    }

    function showTypingIndicator() {
        hideEmptyState();
        var existing = DOM.messageList.querySelector('.typing-indicator');
        if (existing) return;

        var indicator = document.createElement('div');
        indicator.className = 'typing-indicator';
        indicator.innerHTML =
            '<div class="message-avatar">🤖</div>' +
            '<div class="typing-dots">' +
                '<span class="typing-dot"></span>' +
                '<span class="typing-dot"></span>' +
                '<span class="typing-dot"></span>' +
            '</div>';
        DOM.messageList.appendChild(indicator);
        scrollToBottom();
    }

    function hideTypingIndicator() {
        var indicator = DOM.messageList.querySelector('.typing-indicator');
        if (indicator) indicator.remove();
    }

    function scrollToBottom() {
        if (DOM.messageArea) {
            DOM.messageArea.scrollTo({
                top: DOM.messageArea.scrollHeight,
                behavior: 'smooth'
            });
        }
    }

    function updateFilePreview() {
        DOM.attachmentsPreview.innerHTML = '';
        if (attachedFiles.length === 0) {
            DOM.attachmentsPreview.style.display = 'none';
            return;
        }
        DOM.attachmentsPreview.style.display = 'flex';
        attachedFiles.forEach(function (file, idx) {
            var chip = document.createElement('div');
            chip.className = 'file-chip';
            chip.innerHTML =
                '📎 <span class="file-chip-name">' + window.escapeHtml(file.name) + '</span>' +
                '<button class="file-chip-remove" data-idx="' + idx + '">×</button>';
            chip.querySelector('.file-chip-remove').addEventListener('click', function () {
                attachedFiles.splice(idx, 1);
                updateFilePreview();
                updateSendButtonState();
            });
            DOM.attachmentsPreview.appendChild(chip);
        });
    }

    function autoResizeTextarea() {
        var el = DOM.messageInput;
        if (!el) return;
        el.style.height = 'auto';
        el.style.height = Math.min(el.scrollHeight, 144) + 'px';
    }

    function updateSendButtonState() {
        if (!DOM.sendBtn || !DOM.messageInput) return;
        var hasContent = DOM.messageInput.value.trim().length > 0 || attachedFiles.length > 0;
        DOM.sendBtn.disabled = !hasContent || isLoading;
    }

    /* ===== Close export dropdowns on outside click ===== */
    document.addEventListener('click', function () {
        document.querySelectorAll('.export-dropdown-menu.show').forEach(function (el) {
            el.classList.remove('show');
        });
    });

    /* ===== Render Server-Side Messages ===== */
    function renderInitialMessages() {
        /* Read server-rendered data from the hidden script block */
        var dataEl = document.getElementById('initial-data');
        if (!dataEl) return;

        var data;
        try {
            data = JSON.parse(dataEl.textContent);
        } catch (e) {
            console.error('Failed to parse initial data:', e);
            return;
        }

        /* Render initial chat list */
        if (data.chats && data.chats.length > 0) {
            renderChatList(data.chats);
        }

        /* If there's an active chat, render its messages */
        if (data.active_chat) {
            activeChatId = data.active_chat.id;
            activeChatMeta = {
                id: data.active_chat.id,
                title: data.active_chat.title || 'Untitled',
                system_instruction: data.active_chat.system_instruction || ''
            };
            showChatHeader(data.active_chat.title, data.active_chat.id);
            updateActiveSidebarItem(data.active_chat.id);
            DOM.composer.style.display = '';

            if (data.messages && data.messages.length > 0) {
                hideWelcomeScreen();
                hideEmptyState();
                showMessageList();

                data.messages.forEach(function (msg) {
                    var el = createMessageElement(msg, msg.role, data.messages);
                    DOM.messageList.appendChild(el);
                });

                updateRegenerateButtons();
                scrollToBottom();
            } else {
                showEmptyState();
            }
        } else {
            showWelcomeScreen();
            DOM.composer.style.display = 'none';
            hideChatHeader();
            activeChatMeta = null;
        }
    }

    /* ===== Event Binding ===== */
    function bindEvents() {
        /* New Chat button -> open modal */
        if (DOM.newChatBtn) {
            DOM.newChatBtn.addEventListener('click', function () {
                var modal = new bootstrap.Modal(DOM.newChatModal);
                modal.show();
            });
        }

        /* Welcome CTA also opens new chat modal */
        var welcomeCta = document.getElementById('welcome-cta');
        if (welcomeCta) {
            welcomeCta.addEventListener('click', function () {
                var modal = new bootstrap.Modal(DOM.newChatModal);
                modal.show();
            });
        }

        /* Modal form submit */
        if (DOM.newChatForm) {
            DOM.newChatForm.addEventListener('submit', function (e) {
                e.preventDefault();
                createChat();
            });
        }

        /* Send button */
        if (DOM.sendBtn) {
            DOM.sendBtn.addEventListener('click', function () {
                sendMessage();
            });
        }

        /* Textarea keydown */
        if (DOM.messageInput) {
            DOM.messageInput.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });

            DOM.messageInput.addEventListener('input', function () {
                autoResizeTextarea();
                updateSendButtonState();
            });
        }

        /* File attach button */
        if (DOM.attachBtn) {
            DOM.attachBtn.addEventListener('click', function () {
                DOM.fileInput.click();
            });
        }

        /* File input change */
        if (DOM.fileInput) {
            DOM.fileInput.addEventListener('change', function () {
                var files = Array.from(DOM.fileInput.files);
                files.forEach(function (f) {
                    attachedFiles.push(f);
                });
                DOM.fileInput.value = '';
                updateFilePreview();
                updateSendButtonState();
            });
        }

        /* Search input */
        if (DOM.searchInput) {
            DOM.searchInput.addEventListener('input', function () {
                searchChats(DOM.searchInput.value);
            });
        }

        /* Chat title rename (contenteditable-like click) */
        if (DOM.chatTitle) {
            DOM.chatTitle.addEventListener('click', function () {
                if (!activeChatId) return;
                DOM.chatTitle.setAttribute('contenteditable', 'true');
                DOM.chatTitle.focus();

                /* Select all text */
                var range = document.createRange();
                range.selectNodeContents(DOM.chatTitle);
                var sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
            });

            DOM.chatTitle.addEventListener('blur', function () {
                DOM.chatTitle.removeAttribute('contenteditable');
                var newTitle = DOM.chatTitle.textContent.trim();
                var chatId = DOM.chatTitle.getAttribute('data-chat-id');
                var originalTitle = DOM.chatTitle.getAttribute('data-original-title') || '';

                if (!newTitle) {
                    DOM.chatTitle.textContent = originalTitle;
                    return;
                }

                if (newTitle && chatId && newTitle !== originalTitle) {
                    renameChat(chatId, newTitle);
                    DOM.chatTitle.setAttribute('data-original-title', newTitle);
                }
            });

            DOM.chatTitle.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    DOM.chatTitle.blur();
                }
                if (e.key === 'Escape') {
                    DOM.chatTitle.removeAttribute('contenteditable');
                    DOM.chatTitle.textContent = DOM.chatTitle.getAttribute('data-original-title') || '';
                    DOM.chatTitle.blur();
                }
            });
        }

        if (DOM.chatSettingsBtn) {
            DOM.chatSettingsBtn.addEventListener('click', function () {
                openChatSettingsModal();
            });
        }

        if (DOM.chatSettingsForm) {
            DOM.chatSettingsForm.addEventListener('submit', function (e) {
                e.preventDefault();

                if (!activeChatId) return;

                var title = (DOM.chatSettingsTitle.value || '').trim();
                var instruction = (DOM.chatSettingsInstruction.value || '').trim();

                if (!title) {
                    DOM.chatSettingsTitle.focus();
                    return;
                }

                updateChatSettings(activeChatId, title, instruction)
                .then(function () {
                    var modal = bootstrap.Modal.getInstance(DOM.chatSettingsModal);
                    if (modal) modal.hide();
                    window.showToast('Chat settings updated', 'success');
                })
                .catch(function (err) {
                    console.error('updateChatSettings error:', err);
                    window.showToast('Failed to update chat settings', 'error');
                });
            });
        }

        /* Delete button */
        var deleteBtn = document.getElementById('btn-delete-chat');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', function () {
                if (activeChatId) promptDeleteChat(activeChatId);
            });
        }

        /* Confirm delete */
        if (DOM.confirmDeleteBtn) {
            DOM.confirmDeleteBtn.addEventListener('click', function () {
                confirmDeleteChat();
            });
        }
    }

    /* ===== Initialize ===== */
    function init() {
        cacheDom();
        bindEvents();
        renderInitialMessages();
        updateSendButtonState();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    /* ===== Expose for external use ===== */
    window.loadChat = loadChat;
    window.createChat = createChat;
    window.sendMessage = sendMessage;
    window.deleteChat = promptDeleteChat;
})();
