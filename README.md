# gscrap

this is a quick-and-dirty web scrapper for geneanet
imported data are limited to main events (date and place of birth, marriage, death) and to parent

usage: ./scrap.py <maxlevel> <url>

exemple : ./scrap.py 10 'https://gw.geneanet.org/........'

(don't forget quotes around url, or obviously shell will try to handle '&'....)

## licence

GPLv3, see https://www.gnu.org/licenses/gpl-3.0.fr.html

## notes

- tested on french setting only, and only on a few families, expect troubles
- all imported individual has a note with source URL, and share a global note (N9999)
