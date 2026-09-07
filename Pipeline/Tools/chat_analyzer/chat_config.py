"""
Editable configuration for analyze_chat.py
-------------------------------------------
Edit the lists below with your own words. Matching is case-insensitive and
matches whole words only (so "ass" won't match inside "class").
Multi-word entries (e.g. "oh my god") are matched as exact phrases.
"""
import types as _types

# Words counted towards each person's "swears the most" stats.
SWEAR_WORDS = [
    "fuck", "fucking", "fucked", "shit", "damn", "hell", "ass", "asshole", "bitch", "crap", "bastard", "piss", "Retard", "penis", "dick", "cum", "balls", #AI-given
    "Shit", "fuck", "mf", "mofo", "mothernigger", "retard", "ass", "rtrd", "nigger", "nga", "dumbass", "dumbahh", "shitter", "kutte", "kutta", "bc", "mc", "mkc", "bhen ke bhai", "khabees", "fuckass", "duckass", "dumbfuck", "mothertrucker", #Omar-sponsored
]

# Words/tokens counted as "laughing". Add your group's specific ones
# (transliterated laughs, "lmaooo" style stretches are matched via regex below).
LAUGH_WORDS = [
    "haha", "hahaha", "lol", "lmao", "lmfao", "rofl", "hehe", "jajaja", "😂", "😂", "😭",
]
# Regex-style stretch matching: catches "hahahaha", "ahahah", "lmaooooo" etc.
LAUGH_REGEX_PATTERNS = [
    r"\b(?:ha){2,}h?\b",       # haha, hahaha, hahahah
    r"\b(?:he){2,}h?\b",       # hehe, hehehe
    r"\blm(?:f?a)?o+\b",       # lmao, lmfao, lmaoo, lmfaooo
    r"\bl+o+l+\b",             # lol, looool
    r"\bja(?:ja)+\b",          # jajaja
]

# Words that mark a message as a question if the message starts with them
# (in addition to any message containing a "?").
QUESTION_STARTERS = [
    "who", "what", "when", "where", "why", "how", "is", "are", "do", "does",
    "did", "can", "could", "would", "should", "will", "won't", "isn't",
    "aren't", "any", "anyone", "does anyone", "has anyone",
]

# Minimum letters for a word to count in the "most repeated words" analysis.
MIN_WORD_LENGTH = 4

# Minimum number of LETTERS a message must have (after stripping emojis,
# punctuation, and casing) to be eligible as a "repeated phrase". A repeated
# phrase = one whole message, not an n-gram fragment: two messages count as
# the "same phrase" if they're identical once you ignore emojis, punctuation,
# and capitalization (extra whitespace is also collapsed). This means a
# single message that happens to repeat a word many times inside itself
# (e.g. one big "meow meow meow...") only ever counts as ONE occurrence of
# that phrase, not many.
MIN_PHRASE_LENGTH = 8

# Minimum number of times something must be said to be eligible for any
# "most repeated" / "signature" leaderboard (avoids one-off junk entries).
MIN_REPEAT_COUNT = 3

# How many rows to show in each overall "top N" leaderboard (most repeated
# words / most repeated phrases).
TOP_N = 15

# "Signature" words/phrases for the MAIN report and the "Last N Days"
# snapshot are computed PER PERSON (their most personally-owned words and
# phrases), not as a single overall top-N list. Only people with at least
# this many total messages are eligible (avoids drive-by members getting a
# "signature word" off 2 messages), and each eligible person gets up to
# this many entries.
#
# The "Arcs & Mini-arcs" section does NOT use this per-person breakdown —
# a per-person signature word *within* one arc mostly just re-surfaces
# that person's usual words everywhere else too, which is redundant with
# this same per-person list in the main report. Instead, each arc's
# "signature words/phrases" compare that arc's own word frequencies
# against the ENTIRE archive's (see stats_engine.compute_arc_signature_
# stats) to find that specific slice of time's own topic fingerprint. That
# comparative list's length is controlled by TOP_N (LAST_PERIOD_TOP_N for
# arcs), not these two settings.
SIGNATURE_MIN_MESSAGES = 50
SIGNATURE_TOP_N_PER_PERSON = 15

# ---------------------------------------------------------------------------
# "Last N days" snapshot section
# ---------------------------------------------------------------------------
# The report also includes a short snapshot section that re-runs the same
# analysis on just the most recent slice of the archive (see --last-period-
# days on the CLI). That slice naturally has far fewer messages than the
# full history, so the noise-filtering thresholds above (MIN_WORD_LENGTH,
# MIN_REPEAT_COUNT, etc) would filter out almost everything if reused as-is.
# These are the loosened equivalents used ONLY for that snapshot section —
# tune independently of the full-archive settings above.
#
# The same LAST_PERIOD_* thresholds are also reused for the "Arcs &
# Mini-arcs" section (one mini-report per arc/mini-arc from
# arc_report.txt) — arcs/mini-arcs are, just like this snapshot, small
# slices of the full archive, so they need the same loosened noise
# thresholds for the same reason. There's no separate ARC_* set of
# constants; that would just be the same knob duplicated.
LAST_PERIOD_DAYS = 365
LAST_PERIOD_MIN_WORD_LENGTH = 3
LAST_PERIOD_MIN_PHRASE_LENGTH = 8
LAST_PERIOD_MIN_REPEAT_COUNT = 2
LAST_PERIOD_TOP_N = 15
LAST_PERIOD_SIGNATURE_MIN_MESSAGES = 15
LAST_PERIOD_SIGNATURE_TOP_N_PER_PERSON = 10

# A gap of at least this many hours between two consecutive messages counts
# as the earlier one "ending" a conversation and the later one "starting" one.
CONVERSATION_GAP_HOURS = 3

# Hour ranges (24h, inclusive-exclusive) used for "night owl" / "early bird".
NIGHT_OWL_HOURS = (0, 5)     # 0 - 5  =>  12:00am - 4:59am
EARLY_BIRD_HOURS = (5, 10)    # 5 - 10 =>  5:00am - 9:59am

# Words excluded from the "most repeated words" / "signature words"
# leaderboards ONLY — the "biggest vocabulary" unique-word-count metric is
# NOT filtered by this list (all real words still count towards vocabulary).
#
# There's no real part-of-speech tagger in this pipeline (keeps the tool
# dependency-free and fast), so instead this is a deliberately large list of
# pronouns, articles, prepositions, conjunctions, auxiliary/modal verbs,
# common filler verbs & adverbs, and their contractions (with AND without
# the apostrophe, since chat text drops apostrophes constantly — "dont",
# "didnt", "youre" etc). Filtering these out is what gets "most repeated
# words" down to (close to) nouns-only. Add group-specific filler words here
# too. Leave empty to disable filtering entirely.
#
# NOTE: "most repeated words" is no longer just this list's leftovers
# sorted by count — stats_engine compares word rates against a synthetic
# generic-chat baseline (see baseline_corpus.py) to find words THIS chat
# uses noticeably more than a typical chat, not just words said a lot. But
# this list still matters for that: without it, common pronouns/verbs and
# — importantly — this group's own member names (see the block below) would
# swamp that comparative list too, since the synthetic baseline obviously
# never mentions anyone's name and rarely uses "i"/"you"/"the" at chat-like
# rates either. It's also still what the PER-PERSON "signature words"
# tokens are built from. So it's doing double duty, not single duty — keep it.
EXTRA_STOPWORDS = [
    # pronouns
    "i", "im", "ive", "id", "ill", "me", "my", "mine", "myself",
    "you", "youre", "youve", "youd", "youll", "your", "yours", "yourself", "yourselves",
    "he", "hes", "hed", "hell", "him", "his", "himself",
    "she", "shes", "shed", "shell", "her", "hers", "herself",
    "it", "its", "itd", "itll", "itself",
    "we", "were", "weve", "wed", "well", "us", "our", "ours", "ourselves",
    "they", "theyre", "theyve", "theyd", "theyll", "them", "their", "theirs", "themselves",
    "this", "that", "thats", "these", "those",
    "who", "whos", "whom", "whose", "which", "what", "whats",
    "someone", "somebody", "something", "anybody", "anyone", "anything",
    "everybody", "everyone", "everything", "nobody", "nothing", "none", "no one",
    # articles / determiners / quantifiers
    "a", "an", "the", "some", "any", "each", "every", "either", "neither",
    "both", "few", "fewer", "many", "much", "more", "most", "other", "others",
    "another", "such", "all", "several", "enough", "various",
    # conjunctions
    "and", "but", "or", "nor", "so", "yet", "because", "cause", "cuz",
    "although", "though", "since", "unless", "while", "whereas", "if", "than",
    "whether", "therefore", "however", "otherwise", "meanwhile",
    # prepositions
    "about", "above", "across", "after", "against", "along", "among",
    "around", "at", "before", "behind", "below", "beneath", "beside",
    "besides", "between", "beyond", "by", "despite", "down", "during",
    "except", "for", "from", "in", "inside", "into", "near", "of", "off",
    "on", "onto", "out", "outside", "over", "past", "through", "throughout",
    "till", "to", "toward", "towards", "under", "underneath", "until", "up",
    "upon", "with", "within", "without",
    # auxiliary / modal verbs (+ contractions, with & without apostrophe)
    "am", "is", "isnt", "are", "arent", "was", "wasnt", "were", "werent",
    "be", "been", "being",
    "have", "havent", "has", "hasnt", "had", "hadnt", "having",
    "do", "dont", "does", "doesnt", "did", "didnt", "doing",
    "will", "wont", "would", "wouldnt", "shall", "shant", "should",
    "shouldnt", "can", "cant", "cannot", "could", "couldnt", "may", "might",
    "mightnt", "must", "mustnt", "ought", "oughtnt", "lets",
    # here/there + contractions
    "here", "heres", "there", "theres", "where", "wheres",
    # common filler / vague verbs (not nouns even though very frequent)
    "think", "thought", "thinking", "thinks", "know", "knew", "known", "knowing", "knows",
    "want", "wanted", "wanting", "wants", "wanna",
    "going", "goin", "gonna", "gotta", "kinda", "sorta",
    "get", "got", "getting", "gets",
    "make", "made", "making", "makes",
    "say", "said", "saying", "says",
    "tell", "told", "telling", "tells",
    "see", "saw", "seeing", "seen", "sees",
    "look", "looked", "looking", "looks",
    "come", "came", "coming", "comes",
    "go", "went", "gone", "goes",
    "take", "took", "taking", "taken", "takes",
    "give", "gave", "giving", "given", "gives",
    "find", "found", "finding", "finds",
    "feel", "felt", "feeling", "feels",
    "try", "tried", "trying", "tries",
    "ask", "asked", "asking", "asks",
    "need", "needed", "needing", "needs",
    "seem", "seemed", "seeming", "seems",
    "put", "putting", "puts",
    "mean", "meant", "meaning", "means",
    "keep", "kept", "keeping", "keeps",
    "let", "letting", "lets",
    "use", "used", "using", "uses",
    "like", "liked", "liking", "likes",
    # common adverbs / degree words / fillers
    "actually", "really", "literally", "probably", "definitely",
    "seriously", "totally", "basically", "honestly", "obviously",
    "exactly", "clearly", "simply", "maybe", "still", "already", "always",
    "never", "sometimes", "usually", "often", "again", "also", "even",
    "ever", "just", "only", "quite", "rather", "pretty", "very", "too",
    "now", "then", "soon", "later", "today", "tomorrow", "yesterday",
    "away", "back", "around", "together", "instead", "anyway",
    "anyways", "though",
    # short interjections / chat filler
    "yeah", "yea", "yep", "yup", "nah", "nope", "okay", "ok", "okey",
    "oh", "ohh", "hey", "hi", "hii", "hiii", "hello", "bro", "dude",
    "omg", "wow", "damn", "well", "alright", "right", "sure",
]

EXTRA_STOPWORDS += [

    # contractions with apostrophe removed / retained
    "dont", "don't",
    "doesnt", "doesn't",
    "didnt", "didn't",
    "cant", "can't",
    "couldnt", "couldn't",
    "wouldnt", "wouldn't",
    "shouldnt", "shouldn't",
    "wont", "won't",
    "isnt", "isn't",
    "arent", "aren't",
    "wasnt", "wasn't",
    "werent", "weren't",
    "havent", "haven't",
    "hasnt", "hasn't",
    "hadnt", "hadn't",
    "aint", "ain't",

    "thats", "that's",
    "whats", "what's",
    "wheres", "where's",
    "whos", "who's",
    "hows", "how's",
    "theres", "there's",
    "heres", "here's",
    "lets", "let's",

    "youre", "you're",
    "youve", "you've",
    "youd", "you'd",
    "youll", "you'll",

    "im", "i'm",
    "ive", "i've",
    "id", "i'd",
    "ill", "i'll",

    "hes", "he's",
    "hed", "he'd",
    "hell", "he'll",

    "shes", "she's",
    "shed", "she'd",
    "shell", "she'll",

    "were", "we're",
    "weve", "we've",
    "wed", "we'd",
    "well", "we'll",

    "theyre", "they're",
    "theyve", "they've",
    "theyd", "they'd",
    "theyll", "they'll",

    # apostrophe artifacts caused by tokenizers
    "s", "t", "d", "ll", "ve", "re",

    # common question words
    "why",
    "how",
    "when",
    "where",
    "which",
    "what",
    "who",
    "whose",
    "whom",

    # common sentence starters
    "i mean",
    "you know",
    "you see",
    "well",
    "look",
    "listen",
    "basically",
    "honestly",
    "actually",
    "literally",

    # generic conversational verbs
    "want",
    "wants",
    "wanted",
    "need",
    "needs",
    "needed",
    "feel",
    "feels",
    "felt",
    "guess",
    "guessed",
    "guessing",
    "suppose",
    "supposed",
    "hope",
    "hoped",
    "hoping",

    "remember",
    "remembered",
    "forget",
    "forgot",
    "forgotten",

    "believe",
    "believed",
    "believing",

    "understand",
    "understood",
    "understanding",

    "agree",
    "agreed",
    "disagree",
    "disagreed",

    "wonder",
    "wondering",
    "wondered",

    # generic actions
    "bring",
    "brought",
    "buy",
    "bought",
    "sell",
    "sold",
    "send",
    "sent",
    "receive",
    "received",

    "leave",
    "left",
    "stay",
    "stayed",

    "start",
    "started",
    "starting",
    "stop",
    "stopped",

    "happen",
    "happened",
    "happening",

    "work",
    "worked",
    "working",

    "play",
    "played",
    "playing",

    "run",
    "ran",
    "running",

    "move",
    "moved",
    "moving",

    "turn",
    "turned",
    "turning",

    "hold",
    "held",
    "holding",

    "show",
    "showed",
    "showing",

    "check",
    "checked",
    "checking",

    "call",
    "called",
    "calling",

    "change",
    "changed",
    "changing",

    "wait",
    "waited",
    "waiting",

    "help",
    "helped",
    "helping",

    # common chat fillers / reactions
    "lol",
    "lmao",
    "lmfao",
    "rofl",
    "haha",
    "hahaha",
    "hehe",
    "hehehe",
    "xd",
    "xD",
    "bruh",
    "bro",
    "bros",
    "man",
    "mate",

    "yup",
    "yep",
    "yeah",
    "yea",
    "nah",
    "no",
    "yes",

    "ok",
    "okay",
    "k",
    "kk",

    "hmm",
    "hm",
    "hmmm",
    "uh",
    "uhh",
    "umm",
    "ummm",

    # numbers / time chat noise
    "one",
    "two",
    "three",
    "first",
    "second",
    "third",
    "time",
    "times",

    # very common adjectives with little content
    "good",
    "bad",
    "better",
    "best",
    "worse",
    "worst",
    "big",
    "small",
    "little",
    "same",
    "different",
    "new",
    "old",

    # generic nouns that dominate chats
    "thing",
    "things",
    "stuff",
    "way",
    "ways",
    "part",
    "place",
    "point",
    "idea",
    "reason",
    "person",
    "people",
    "guy",
    "guys",

    # common internet/chat words
    "message",
    "messages",
    "chat",
    "group",
    "bro",
    "lol",
    "irl",
    "btw",
    "idk",
    "ikr",
    "imo",
    "imho",
    "tbh",
    "ngl",
    "fr",
    "frfr",

]

EXTRA_STOPWORDS += [
    "Akif", "akif",
    "Ahmed", "ahmed",
    "Nasser", "nasser",
    "Tariq", "tariq",
    "Omar", "omar",
    "Umer", "umer",
    "Omer", "omer",
    "Umar", "umar",
    "Ahsan", "ahsan",
    "Shabeeb", "shabeeb",
    "Hashem", "hashem",
    "Hashim", "hashim",
    "Ali", "ali",
    "Alizaman", "alizaman",
    "Rafay", "rafay",
    "Abdullah", "abdullah",
    "AbdulRafay", "abdulrafay",
    "Abdulrafay", "abdulrafay",
    "Numan", "numan",

]


def make_profile(**overrides):
    """Returns a namespace snapshot of every SETTING (i.e. every upper-case
    constant) in this module, with any of the given keyword overrides
    applied on top. Used to run the stats_engine functions with different
    noise thresholds without editing this file — e.g. the built-in "last N
    days" snapshot section, or one-off CLI flags like --top-n /
    --min-repeat-count for a custom slice.

    Usage: chat_config.make_profile(MIN_REPEAT_COUNT=2, TOP_N=10)
    """
    ns = _types.SimpleNamespace(**{k: v for k, v in globals().items() if k.isupper()})
    for k, v in overrides.items():
        setattr(ns, k.upper(), v)
    return ns
