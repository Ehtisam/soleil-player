# Languages

The device's main language is Turkish. Each folder here is a second language, chosen under Sistem Ayarları > Dil (System Settings > Language).

```
dil/
  solainwen/
    dil.json     name, alphabet, font
    ceviri.md    translation table (filled in with Obsidian)
    font.ttf     the alphabet's font (once it is ready)
```

The folder name is the language code, and the settings show the `"ad"` (name) field from `dil.json`. To give it a different name, change both the folder and `"ad"`.

## Translation table: ceviri.md

The left column holds the Turkish text and the right column holds the **pronunciation of the language in Latin letters**. Rows left empty show in Turkish, so the table can be filled in bit by bit.

- Case does not matter: once "Sistem Ayarları" is translated, "SİSTEM AYARLARI" is translated too.
- Placeholders such as `{n}` (a number or a name) must stay as they are in the translation: `{n} şarkı` becomes `{n} norae`.
- When new text is added to the code, the table is updated with `python tools/ceviri_listesi.py solainwen`. Rows that are already filled in are left alone.
- Things you write yourself, such as song names, notes, books and device names, are not translated.

## Alphabet: dil.json > "alfabe"

The pronunciation is split into syllable blocks, one block per syllable. Solainwen has three block types:

- **Standard:** a consonant at the top left and a vowel at the top right. If the syllable ends with a consonant, a special consonant (`"son"`) runs across the bottom. The vowel never moves to the bottom.
- **Vowel only:** the vowel fills the whole block (the e in "ego", the au in "auru").
- **Starting with a vowel:** the block is split down the middle, with the vowel on the left and the consonant on the right ("il", "an"). This consonant can be a special consonant or a normal one ("ag").

Lists:

- `"ilk"`: consonants at the start of a syllable, clusters included (STR, PH...)
- `"orta"`: vowels, including combined vowels and the special vowel (EAU, UAI, EG). Each one is a single mark
- `"son"`: special consonants at the end of a syllable, clusters included (NT, NG...)
- `"yerlesim"` (optional): the proportions of the places inside a block. Without it, `LAYOUTS` in `soleil/script.py` is used. The top middle slot of the standard block is unused for now

Syllable rule: of the consonants between two vowels, the longest part that can start a syllable moves to the next syllable, and the rest ends the previous one ("maison" becomes mai-son, "sento" becomes sen-to). Letter groups are read by the longest match ("beau" is one block). When EG is followed by a vowel, e and g are split ("ego" becomes e-go). EG is the special vowel only at the end or before a consonant. Consonants that cannot attach to any syllable (the g in "dog", because G cannot end a syllable), W, digits and punctuation stay in Latin.

To see how a text is split into blocks:

```
python tools/blok_onizleme.py "maison de ego" "spada de auru"
```

## Font: font.ttf

Without a font, the blocks are drawn as a **sketch** with small Latin letters, which is enough to see the layout.

Once the font is ready, each letter sits at these characters in the font (in the order of the lists in dil.json):

| | First character |
|---|---|
| Initial sounds | U+E000 (1st initial sound), U+E001 (2nd), ... |
| Vowels | U+E100, U+E101, ... |
| Special consonants | U+E200, U+E201, ... |

If the letters are drawn in Figma and exported as SVG, the font is built from them. The code scales each letter and places it in its spot in the block.
