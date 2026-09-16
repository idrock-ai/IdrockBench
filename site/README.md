# eval.idrock.uz

The public leaderboard. Static site, no framework.

```bash
cd site
npm run build      # -> dist/, with content-hashed asset URLs
npx serve dist
```

## results.json is generated, never edited

```bash
idrockbench report --suite core        # writes site/results.json
```

It is rebuilt from `runs/` in full on every publish. A cell that no run
produced cannot appear, and deleting a run removes it from the board.

**Do not edit it by hand.** The previous leaderboard was maintained that way,
and twenty of its fifty cells had no source run.

## What the page renders

The table follows the data. Columns come from `tasks` in `results.json`, so a
task added to the suite appears without touching the HTML - and a task removed
from the suite disappears rather than lingering as an empty column.

Each cell shows the score, its 95% interval and its sample size. Two flags:

- `⚠` - at or below the task's random baseline. Usually a broken extractor.
- `◐` - under 80% of items were scorable. The number reflects response format
  as much as model quality.

Ranks are read from the file, never recomputed when a reader sorts a column.
Models without a complete run are shown unranked, below the ranked rows.
