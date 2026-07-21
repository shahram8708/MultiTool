/**
 * MultiTool AI — Markdown Rendering Module
 * Configures marked.js with highlight.js for syntax highlighting
 * and DOMPurify for safe HTML output.
 */
(function () {
    'use strict';

    /**
     * Configure marked.js renderer with highlight.js integration
     * and enhanced code block rendering with copy buttons.
     */
    function configureMarked() {
        const renderer = new marked.Renderer();

        /* Enhanced code block rendering with language label and copy button */
        renderer.code = function (code, language) {
            /* marked v12+ passes an object {text, lang} as first arg sometimes */
            let text, lang;
            if (typeof code === 'object' && code !== null) {
                text = code.text || '';
                lang = code.lang || language || '';
            } else {
                text = code || '';
                lang = language || '';
            }

            const validLang = lang && hljs.getLanguage(lang);
            let highlighted;
            try {
                highlighted = validLang
                    ? hljs.highlight(text, { language: lang, ignoreIllegals: true }).value
                    : hljs.highlightAuto(text).value;
            } catch (e) {
                highlighted = escapeHtmlBasic(text);
            }

            const displayLang = lang ? lang : 'code';
            const escapedCode = text.replace(/'/g, '&#39;').replace(/"/g, '&quot;');

            return (
                '<div class="code-block-wrapper">' +
                    '<div class="code-block-header">' +
                        '<span>' + escapeHtmlBasic(displayLang) + '</span>' +
                        '<button class="btn-copy-code" onclick="window.copyCodeBlock(this)" data-code="' + encodeCopyData(text) + '">Copy</button>' +
                    '</div>' +
                    '<pre><code class="hljs language-' + escapeHtmlBasic(displayLang) + '">' + highlighted + '</code></pre>' +
                '</div>'
            );
        };

        /* Ensure links open in new tab */
        renderer.link = function (href, title, text) {
            /* marked v12+ passes object as first arg */
            let url, linkTitle, linkText;
            if (typeof href === 'object' && href !== null) {
                url = href.href || '';
                linkTitle = href.title || '';
                linkText = href.text || '';
            } else {
                url = href || '';
                linkTitle = title || '';
                linkText = text || '';
            }
            const titleAttr = linkTitle ? ' title="' + escapeHtmlBasic(linkTitle) + '"' : '';
            return '<a href="' + url + '"' + titleAttr + ' target="_blank" rel="noopener noreferrer">' + linkText + '</a>';
        };

        marked.setOptions({
            renderer: renderer,
            breaks: true,
            gfm: true,
            pedantic: false,
            smartypants: false,
            headerIds: false,
            mangle: false
        });
    }

    /**
     * Basic HTML escaping for use inside code rendering.
     */
    function escapeHtmlBasic(str) {
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
        return String(str).replace(/[&<>"']/g, function (m) { return map[m]; });
    }

    /**
     * Encode code text for safe embedding in data attributes.
     */
    function encodeCopyData(text) {
        return btoa(unescape(encodeURIComponent(text)));
    }

    /**
     * Decode code text from data attribute.
     */
    function decodeCopyData(encoded) {
        try {
            return decodeURIComponent(escape(atob(encoded)));
        } catch (e) {
            return encoded;
        }
    }

    /**
     * Copy code block content to clipboard.
     * Attached to window for onclick access from rendered HTML.
     */
    window.copyCodeBlock = function (btn) {
        var encoded = btn.getAttribute('data-code');
        var code = decodeCopyData(encoded);

        navigator.clipboard.writeText(code).then(function () {
            var orig = btn.textContent;
            btn.textContent = 'Copied!';
            btn.style.color = 'var(--success)';
            setTimeout(function () {
                btn.textContent = orig;
                btn.style.color = '';
            }, 2000);
        }).catch(function () {
            /* Fallback for older browsers */
            var ta = document.createElement('textarea');
            ta.value = code;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            var orig = btn.textContent;
            btn.textContent = 'Copied!';
            setTimeout(function () { btn.textContent = orig; }, 2000);
        });
    };

    /**
     * Render markdown text to sanitized HTML.
     * @param {string} text - Raw markdown string
     * @returns {string} Sanitized HTML string
     */
    function renderMarkdown(text) {
        if (!text || typeof text !== 'string') return '';

        var rawHtml;
        try {
            rawHtml = marked.parse(text);
        } catch (e) {
            console.error('Markdown parse error:', e);
            rawHtml = '<p>' + escapeHtmlBasic(text) + '</p>';
        }

        /* Sanitize with DOMPurify, allowing safe HTML for formatted content */
        var clean = DOMPurify.sanitize(rawHtml, {
            ALLOWED_TAGS: [
                'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                'p', 'br', 'hr',
                'strong', 'b', 'em', 'i', 'u', 's', 'del', 'ins', 'mark', 'sub', 'sup',
                'ul', 'ol', 'li',
                'blockquote', 'pre', 'code',
                'a', 'img',
                'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td',
                'div', 'span',
                'details', 'summary',
                'dl', 'dt', 'dd',
                'button'
            ],
            ALLOWED_ATTR: [
                'href', 'target', 'rel', 'title',
                'src', 'alt', 'width', 'height',
                'class', 'id', 'style',
                'colspan', 'rowspan',
                'data-code', 'onclick',
                'open'
            ],
            ALLOW_DATA_ATTR: true,
            ADD_ATTR: ['target']
        });

        return clean;
    }

    /* Initialize marked on load */
    configureMarked();

    /* Expose globally */
    window.renderMarkdown = renderMarkdown;
})();
