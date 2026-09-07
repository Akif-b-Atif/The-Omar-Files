# Sample data

Don't have a WhatsApp export handy but want to see what the pipeline
actually produces? These files are fake, generated data (5 fictional
people, ~5,600 messages, spanning January to August 2025) formatted
exactly like a real WhatsApp export, so you can run the full pipeline
against them right away and get a real, complete set of reports.

It's not just random noise, either — it's shaped to actually surface
something when analyzed:

- One clear high-activity **Arc** and one smaller **Mini-arc**, so
  `arc_analyzer` has something real to detect (see
  `docs/ARCHITECTURE.md` / `Pipeline/Tools/arc_analyzer/TECHNICAL.md`
  for what those are).
- A running inside joke ("the mango incident") repeated enough times
  to show up in the "most repeated phrases" stats.
- Distinct per-person habits: some people talk a lot more than others,
  one's a clear night owl, activity is heavier on some days than
  others.
- One person (Kabir) shows up under his raw phone number for part of
  the second file instead of his name, the way an unsaved contact
  looks in a real export, to demonstrate the identity/alias
  resolution feature (`identities.sample.json` below already resolves
  it, so you don't have to).

None of this is meant to be realistic conversation, just structured
enough that the reports show real, non-trivial patterns instead of
flat noise. Don't expect it to compete with your actual 300k-message
group chat.

## Using it

From the project root:

```
cp sample_data/01_sample_export_part1.txt Raw_Exports/
cp sample_data/02_sample_export_part2.txt Raw_Exports/
cp sample_data/identities.sample.json Pipeline/identities.json
cd Pipeline
pip install -r requirements.txt --break-system-packages
python3 control.py merge 01_sample_export_part1.txt 02_sample_export_part2.txt
python3 control.py reports
```

That builds `Full_Archive.txt` / `Full_Archive.pdf` and every report
(`chat_report.html`, `chat_report.pdf`, `arc_report.txt`,
`arc_timeline.png`) at the project root, exactly like a real run would.
Open `chat_report.html` in a browser (or run the small local server it
tells you to, if the Explorer tab can't load its data over `file://`)
to look around.

`identities.sample.json` is just a starting `identities.json` with the
five sample senders (and Kabir's phone-number alias) already resolved,
copied in so you don't hit the interactive "who is this?" prompts
`2_normalize_export.py` would otherwise ask about unfamiliar sender
labels the first time through. See "The identities.json model" in
`Pipeline/TECHNICAL.md` for how that file works once you move on to
your own real export.

## Trying it on your own chat afterward

Once you're ready to use your own data: copy `Pipeline/identities.example.json`
to `Pipeline/identities.json` instead (overwriting the sample one, or
just clearing it out and starting fresh), drop your own export(s) into
`Raw_Exports/`, and run the same commands above with your own
filenames. See the root `README.md`'s "Setting this up for your own
chat" section for the full walkthrough.
