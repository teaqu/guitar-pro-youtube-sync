`faint-dead-beat.json` is the unmodified second beat of measure 9 from
Linkin Park's Faint, Songsterr song 502, revision 9803522, part index 2
(Brad Delson lead guitar), retrieved 2026-11-15:

https://dqsljvtekg760.cloudfront.net/502/9803522/v0-3-2-iUVyfOENF2nzO4jf/2.json

The middle note has `dead: true` while retaining fret 7 and string 3.
The neighboring strings remain normal notes. The beat lasts an eighth note.
GPIF represents this as `Property name="Muted"` containing `Enable` on
that individual Note, separate from `PalmMuted` and ghost `AntiAccent`.
Reference GPIF reader and Guitar Pro fixture:

- https://github.com/CoderLine/alphaTab/blob/develop/packages/alphatab/src/importer/GpifParser.ts
- https://github.com/CoderLine/alphaTab/blob/develop/packages/alphatab/test-data/guitarpro7/dead.gp
