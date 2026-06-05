"""Helper: render an e-mail address as HTML that bots cannot parse but JS decodes.

The address is stored in `data-u` / `data-d` attributes (user/domain),
each character-reversed. A small script in js/main.js reads the attributes,
reverses them again, and writes a real mailto: link plus visible text.

Without JavaScript, the link shows a placeholder text like "E-Mail anzeigen"
and the actual address is never visible to spam scrapers crawling the HTML.
"""


def obfuscate_mailto(email, placeholder_de="E-Mail anzeigen", placeholder_en=None):
    """Return an HTML <a class="eml"> element with reversed user/domain in data-*.

    The visible text is the placeholder until JS runs; once decoded, it shows the
    plain address.
    """
    if not email or "@" not in email:
        return ""
    user, domain = email.split("@", 1)
    user_r   = user[::-1]
    domain_r = domain[::-1]
    placeholder = placeholder_en if placeholder_en is not None else placeholder_de
    return (
        f'<a class="eml" href="#" data-u="{user_r}" data-d="{domain_r}" '
        f'rel="noopener">{placeholder}</a>'
    )
