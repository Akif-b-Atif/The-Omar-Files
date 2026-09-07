"""
A synthetic, totally generic group-chat conversation used ONLY as a
statistical baseline for "what does a normal group chat sound like".

Why this exists: "most repeated words" used to just mean "every word said
a lot, minus pronouns/prepositions/auxiliary verbs" (via EXTRA_STOPWORDS in
chat_config.py). But once you strip those out, what's left is STILL mostly
universal chat filler -- "lol", "yeah", "literally", "dinner", "weekend" --
because literally every group chat on Earth says those constantly. That's
not "this group's most repeated words", it's just "words all group chats
repeat".

This file is ~1000 lines of a made-up, generic group chat -- no names, no
inside jokes, no specific topics/hobbies, just the ordinary logistics/
reactions/small-talk any group chat produces. stats_engine.py tokenizes it
once, counts word frequency, and compares the REAL archive's word rates
against these baseline rates. A word that's said at roughly the same rate
here as in the real chat is just normal chat noise; a word said at a much
HIGHER rate in the real chat is something that chat specifically talks
about a lot -- names, hobbies, running jokes, places, etc. -- which is
what "most repeated words" is actually supposed to surface.

Nothing here needs WhatsApp's timestamp/sender format -- only the text of
each "message" is ever used (for word-frequency counting), so this is
just a flat list of strings, one per message.
"""
import itertools

# Generic standalone lines: greetings, reactions, logistics, small talk.
# Deliberately bland/universal -- if a real group chat said any of these
# a lot too, that's exactly the kind of thing this baseline should
# absorb so it DOESN'T show up as a "signature word".
_PLAIN_LINES = [
    "hey what's up", "yo whats good", "morning everyone", "good morning",
    "good night guys", "night everyone", "lol yeah for sure", "haha true",
    "omg no way", "wait what happened", "wait really", "no way that's crazy",
    "same tbh", "same here honestly", "i feel that", "big mood",
    "lmaooo stop", "im dying", "im crying rn", "this is so funny",
    "not funny at all", "that's actually so sad", "aw that sucks",
    "hope you feel better soon", "get well soon", "sending good vibes",
    "congrats!!", "congratulations to you", "so proud of you", "well deserved",
    "you did amazing", "that's awesome news", "love this for you",
    "what time works for everyone", "what time are we meeting",
    "can we push it back an hour", "can we do it earlier instead",
    "i might be a little late", "running late sorry", "on my way now",
    "just left the house", "almost there", "here now where are you",
    "i'm outside", "give me five minutes", "give me ten minutes",
    "be there soon", "traffic is insane right now", "traffic is so bad today",
    "the weather is terrible today", "it's freezing outside", "it's so hot today",
    "it's raining again", "forecast says it'll rain all week",
    "does anyone have an umbrella", "bring a jacket it's cold",
    "what should we eat tonight", "i'm starving right now",
    "let's just order food", "should we get pizza", "pizza sounds good honestly",
    "i could eat literally anything", "i'm not that hungry", "already ate sorry",
    "save me some leftovers", "that food looks so good", "where should we eat",
    "any restaurant recommendations", "that place is overrated honestly",
    "that place is actually really good", "we should go there again sometime",
    "can we go somewhere new this time", "i'm down for whatever",
    "i don't mind either way", "you guys decide i'll follow",
    "let's just vote on it", "majority rules i guess",
    "who's free this weekend", "what's everyone doing this weekend",
    "i have nothing planned", "i'm free all weekend honestly",
    "i have plans already sorry", "maybe next weekend instead",
    "can we reschedule for next week", "next week works better for me",
    "i'm swamped this week", "work has been so busy lately",
    "school has been so busy lately", "so much going on right now",
    "i need a break so bad", "i'm exhausted honestly", "i barely slept last night",
    "i slept in so late today", "i woke up so early today",
    "i can't fall asleep lately", "i need more sleep fr",
    "my phone died earlier", "my phone is at 1 percent",
    "sorry just saw this", "sorry missed this earlier", "just saw your message",
    "didn't see this till now", "my bad totally missed it",
    "no worries at all", "it's all good", "don't worry about it",
    "all good no stress", "take your time no rush",
    "quick question for everyone", "random question but", "unrelated but",
    "slightly off topic but", "anyway back to the actual topic",
    "wait i have a question", "does anyone know the answer to this",
    "can someone help me with this", "i'm so confused right now",
    "that makes so much sense now", "oh i get it now", "ohh gotcha",
    "makes sense thanks", "thank you so much", "thanks appreciate it",
    "appreciate you for that", "you're the best honestly", "love you guys",
    "this group chat is unhinged", "why is this group so quiet today",
    "why is no one responding", "hello is anyone there", "anyone home",
    "bumping this in case people missed it", "just a reminder about this",
    "friendly reminder for everyone", "don't forget about this please",
    "did everyone see this", "can everyone confirm they saw this",
    "please respond when you can", "let me know your thoughts",
    "what does everyone think", "thoughts on this anyone",
    "i honestly have no opinion", "i'm neutral on this one",
    "i actually disagree a bit", "i see it differently honestly",
    "fair point though", "that's a good point actually", "never thought of it that way",
    "i guess that's true", "i mean you're not wrong", "valid point tbh",
    "can we talk about something else", "changing the subject real quick",
    "on a completely different note", "speaking of something else entirely",
    "did you guys watch that show", "did you see that video",
    "that video was hilarious", "i can't stop watching that",
    "someone sent me the funniest thing today", "you have to see this",
    "i'll send it in a sec", "sending it now hold on",
    "check your messages", "did you get my message", "check your email please",
    "did you get the email i sent", "i sent it a while ago",
    "let me resend it", "here you go", "here's the link",
    "here's what i meant", "that's exactly what i meant",
    "i'm going to bed now", "heading to sleep now", "logging off for the night",
    "talk to you all tomorrow", "see everyone tomorrow", "catch you guys later",
    "gtg talk later", "have to go now bye", "brb one sec",
    "back now sorry about that", "ok i'm back", "back from the gym",
    "just got out of class", "just got off work", "leaving work now",
    "finally off work", "long day at work today", "long day honestly",
    "today was rough", "today was actually pretty good", "not a bad day overall",
    "could've been worse honestly", "it is what it is", "such is life",
    "can't complain honestly", "living the dream lol", "barely surviving tbh",
    "one of those days", "one of those weeks honestly", "so ready for the weekend",
    "weekend can't come soon enough", "is it friday yet", "almost friday",
    "monday already ugh", "back to the grind", "here we go again",
]

# Sentence templates + a small bank of generic filler "topics" -- combined
# to pad this out to roughly a thousand generic messages without hand
# writing a thousand distinct lines. None of these topics are specific to
# any one group's actual interests -- they're the same handful of things
# (work, school, food, weather, generic events) every group chat mentions.
_TEMPLATES = [
    "are we still doing {topic} later",
    "i can't believe {topic} today",
    "who else is going to {topic}",
    "can we move {topic} to tomorrow",
    "just got back from {topic}",
    "not gonna lie {topic} was rough today",
    "does anyone have notes from {topic}",
    "i'm so tired after {topic}",
    "{topic} got cancelled again",
    "see you all at {topic}",
    "how was {topic} today",
    "{topic} was actually kind of fun",
    "i'm dreading {topic} tomorrow",
    "can't wait for {topic} honestly",
    "forgot {topic} was today",
    "reminder that {topic} starts soon",
    "{topic} ran way longer than expected",
    "who's coming with me to {topic}",
    "i might skip {topic} this time",
    "{topic} was such a mess today",
    "let's talk about {topic} for a sec",
    "any updates on {topic}",
    "i have {topic} in an hour",
    "just finished {topic} finally",
    "{topic} is stressing me out honestly",
]

_TOPICS = [
    "work", "school", "class", "practice", "the game", "the meeting",
    "dinner", "the gym", "the movie", "the trip", "the party", "the exam",
    "traffic", "the weekend", "the concert", "the wedding", "training",
    "the interview", "the flight", "the appointment", "the project",
    "the presentation", "the errand", "the drive over", "lunch",
    "the group project", "the assignment", "practice tonight", "the shift",
    "the commute",
]


def _build():
    lines = list(_PLAIN_LINES)
    for tmpl, topic in itertools.product(_TEMPLATES, _TOPICS):
        lines.append(tmpl.format(topic=topic))
    return lines


# ~150 plain lines + 25 templates x 30 topics (750 combos) = ~900 messages.
# "Not too long, like 1000 or so" per the brief -- this is a synthetic
# baseline for word-frequency comparison, not a real transcript, so exact
# message count doesn't matter as long as it's a large, generic sample.
BASELINE_MESSAGES = _build()
