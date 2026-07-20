# fmhy-config

The source list TV compatible FMHY links. It does this by reading the FMHY github and generating urls for a list we know works on TV. 

## Editing the list

All logic is in `generate.py`. Order is important as the Categories show in the order you list them and FALLBACK in the order theyre listed too.

Name the sources yourself, in fallback order:

```python
{"name": "Desi Movies", "items": ["MultiMovies", "Desicinemas", "67Movies", "456movie"]},
```

Each name is a source is CASE SENSITIVE to how FMHY writes it, and each becomes its own row carrying its own mirrors,
so `67Movies` keeps its `67movies.net` for example but the 3 other mirrors are dynamically fetched and updated mirror without you typing it.If a source is not on FMHY, put a full `https://` url in place of the name.

Or take a whole FMHY section as-is:

```python
{"name": "Anime", "from": "Anime Streaming"},
```

Every starred source under that heading becomes a row.

## Running it

    python generate.py --check    # build it, print what you'd get, write nothing
    python generate.py            # write config.json

No dependencies, just the standard library.

It stops with an error if a page will not load, a `from` heading has disappeared, or a category comes out empty, so a bad edit fails the run instead of shipping an empty app. One source going missing from FMHY is only a warning.
