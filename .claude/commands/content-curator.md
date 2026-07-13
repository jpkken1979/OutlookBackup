# /content-curator — Content Curator Agent Commands

Monitors Japanese regulatory RSS feeds for dispatch law updates, labor standards changes, and HR news.

## Actions

```
/content-curator status          Show last scan results and configured feeds
/content-curator scan           Force a scan of all RSS feeds now
/content-curator add-feed <url>  Add a custom RSS feed to monitor
```

## Examples

```
/content-curator status
/content-curator scan
/content-curator add-feed https://www.mhlw.go.jp/rss/new.xml
```

## Notes

- Keywords: 派遣, 個別契約書, 労働基準法, 賃金, 労働契約
- Feeds: MHLW, Hello Work, NHK News
- Results ingested to Brain Network automatically
- Run `python .agent/agents/content-curator/scripts/scheduler.py --interval 4` for continuous monitoring