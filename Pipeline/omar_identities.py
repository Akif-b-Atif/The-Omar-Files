"""
omar_identities.py -- identity/alias helpers shared by the archive pipeline
(scripts/) and the analyzer (Tools/chat_analyzer/).

Both sides need to agree on what "the same alias" means, so the key
function and the alias-map builder live here instead of being re-derived
(slightly differently) in each place.
"""
import re
import unicodedata

# Unicode directional isolates. WhatsApp wraps the contact name in an
# @-mention like "@<FSI>Name<PDI>". They're invisible, but they're what
# lets a mention label contain spaces, so they have to survive parsing
# until mentions are resolved -- see common.resolve_mentions().
FSI = "\u2068"
PDI = "\u2069"
ISOLATE_CHARS_RE = re.compile("[\u2066-\u2069]")

# WhatsApp prefixes the label of someone who isn't a saved contact with
# "~" plus a (narrow) no-break space.
_NON_CONTACT_PREFIX_RE = re.compile(r"^~[\s\u202f\u00a0]*")
# Emoji variation selectors: "❤" and "❤️" are the same label to a human.
_VARIATION_SELECTORS_RE = re.compile("[\ufe0e\ufe0f]")


def strip_isolates(text):
    return ISOLATE_CHARS_RE.sub("", text)


def alias_key(label):
    """Canonical lookup key for a sender label / alias / mention label:
    isolates, variation selectors and the non-contact "~ " prefix removed,
    NFKC-normalized, casefolded. Every alias_map lookup goes through this
    so "Akifa❤️" == "akifa❤" and "AKIF BIN ATIF" == "Akif Bin Atif"."""
    label = strip_isolates(label)
    label = _VARIATION_SELECTORS_RE.sub("", label)
    label = _NON_CONTACT_PREFIX_RE.sub("", label.strip())
    return unicodedata.normalize("NFKC", label).strip().casefold()


def build_alias_map(data):
    """Builds {alias_key: canonical_name} from a loaded identities.json
    dict. Every canonical name is an implicit alias of itself, so an
    already-normalized file (whose senders are canonical names) resolves
    without each name being listed in its own alias list.

    Returns (alias_map, conflicts). `conflicts` maps every key claimed by
    more than one DIFFERENT identity to the set of names claiming it. The
    alias_map keeps the first claimant for those keys; callers that would
    rather not guess (the analyzer) can drop the conflicting keys."""
    claims = {}
    for person in data.get("identities", []):
        canonical = person["name"]
        for label in [canonical, *person.get("aliases", [])]:
            key = alias_key(label)
            if key:
                claims.setdefault(key, {})[canonical] = True
    alias_map, conflicts = {}, {}
    for key, names in claims.items():
        alias_map[key] = next(iter(names))
        if len(names) > 1:
            conflicts[key] = set(names)
    return alias_map, conflicts
