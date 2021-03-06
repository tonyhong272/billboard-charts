#!/usr/bin/env python
import json
import requests
from bs4 import BeautifulSoup

"""billboard.py: Unofficial Python API for accessing ranking charts from Billboard.com."""

__author__ = "Allen Guo"
__license__ = "MIT"
__maintainer__ = "Allen Guo"
__email__ = "guoguo12@gmail.com"


HEADERS = {'User-Agent': 'billboard.py (https://github.com/guoguo12/billboard-charts)'}


class ChartEntry:
    """Represents a single entry (song) on a chart.

    Attributes:
        title: The title of the song.
        artist: The name of the song artist, as formatted on Billboard.com.
            If there are multiple artists and/or featured artists, they will
            be included in this string.
        peakPos: The song's peak position on the chart, as an int.
        lastPos: The song's position on the chart last week, as an int.
            This value is 0 if the song has never been on the chart before.
        weeks: The number of weeks the song has been on the chart.
            This value is 1 if the song is new on the chart.
        rank: The song's current position on the chart.
        change: A string indicating how the song's position has changed since
            last week. This may be of the form '+n' or '-n', where 'n' is an
            integer; this indicates that the song's position has increased
            or decreased by 'n' points. This string could also be 'New' or
            'Re-Entry'; this indicates that the song wasn't on the chart last
            week because it is either completely new to the chart or
            re-entering the chart after leaving it for at least a week.
            Additionally, this string is 'Hot Shot Debut' for the
            highest-ranked 'New' song.
        spotifyLink: the link for spotify track.
    """

    def __init__(self, title, artist, peakPos, lastPos, weeks, rank, change, spotifyLink):
        """Constructs a new ChartEntry instance with given attributes.
        """
        self.title = title
        self.artist = artist
        self.peakPos = peakPos
        self.lastPos = lastPos
        self.weeks = weeks
        self.rank = rank
        self.change = change
        self.spotifyLink = spotifyLink

    def __repr__(self):
        """Returns a string of the form 'TITLE by ARTIST'.
        """
        return "'%s' by %s" % (self.title, self.artist)

    def to_JSON(self):
        """Returns the entry as a JSON string.
        This is useful for caching.
        """
        return json.dumps(self, default=lambda o: o.__dict__,
                          sort_keys=True, indent=4)


class ChartData:
    """Represents a particular Billboard chart for a particular date.
    """

    def __init__(self, name, date=None, fetch=True, all=False):
        """Constructs a new ChartData instance.

        By default, this constructor will download the requested data from
        Billboard.com by calling fetchEntries().

        Args:
            name: The chart name, e.g. 'hot-100' or 'pop-songs'.
                You can browse the Charts section of Billboard.com to find
                valid chart names; the URL of a chart will look like
                "http://www.billboard.com/charts/CHART-NAME".
            date: The chart date as a string, in YYYY-MM-DD format.
                If this argument is omitted, the latest chart will be fetched.
                Again, the best way to find valid dates is by browsing the
                Billboard website. An example of a valid date is '2015-11-28',
                which gets the chart viewable at
                http://www.billboard.com/charts/hot-100/2015-11-28.
                If this argument is invalid, no exception will be raised;
                instead, the chart will contain no entries.
            fetch: A boolean indicating whether to fetch the chart data from
                Billboard.com immediately (at instantiation time).
                If False, the chart data can be populated at a later time
                using the fetchEntries() method.
            all: Deprecated; has no effect.
        """
        self.name = name
        self.previousDate = None
        if date:
            self.date = date
            self.latest = False
        else:
            self.date = None
            self.latest = True
        self.entries = []
        if fetch:
            self.fetchEntries(all=all)

    def __repr__(self):
        """Returns the chart as a human-readable string (typically multi-line).
        """
        if self.latest:
            s = '%s chart (current)' % self.name
        else:
            s = '%s chart from %s' % (self.name, self.date)
        s += '\n' + '-' * len(s)
        for n, entry in enumerate(self.entries):
            s += '\n%s. %s (%s)' % (entry.rank, str(entry), entry.change)
        return s

    def __getitem__(self, key):
        """Returns the (key + 1)-th chart entry; i.e., chart[0] refers to the
        song at the No. 1 (top) position on the chart.
        """
        return self.entries[key]

    def __len__(self):
        """Returns the number of entries in the chart.
        A length of zero may indicated a failed/bad request.
        """
        return len(self.entries)

    def to_JSON(self):
        """Returns the entry as a JSON string.
        This is useful for caching.
        """
        for entry in self.entries:
            entry = entry.to_JSON()
        return json.dumps(self, default=lambda o: o.__dict__,
                          sort_keys=True, indent=4)

    def fetchEntries(self, all=False):
        """GETs the corresponding chart data from Billboard.com, then parses
        the data. Makes use of BeautifulSoup.
        """
        if self.latest:
            url = 'http://www.billboard.com/charts/%s' % (self.name)
        else:
            url = 'http://www.billboard.com/charts/%s/%s' % (
                self.name, self.date)

        html = downloadHTML(url)
        soup = BeautifulSoup(html, 'html.parser')

        prevLink = soup.find('a', {'title': 'Previous Week'})
        if prevLink:
            # Extract the previous date from the link. 
            # eg, /charts/country-songs/2016-02-13
            self.previousDate = prevLink.get('href').split('/')[-1]
            
        currentTime = soup.find('time')
        if currentTime:
            # Extract the previous date from the link. 
            # eg, /charts/country-songs/2016-02-13
            self.date = currentTime.get('datetime')
            
        for entry_soup in soup.find_all('article', {'class': 'chart-row'}):
            # Grab title and artist
            basicInfoSoup = entry_soup.find('div', 'chart-row__title').contents
            title = basicInfoSoup[1].string.strip()

            if (basicInfoSoup[3].find('a')):
                artist = basicInfoSoup[3].a.string.strip()
            else:
                artist = basicInfoSoup[3].string.strip()

            def getRowValue(rowName):
                return entry_soup.select_one('div.chart-row__' + rowName + ' .chart-row__value').string.strip()

            # Grab week data (peak rank, last week's rank, total weeks on
            # chart)
            peakPos = int(getRowValue('top-spot'))

            lastPos = getRowValue('last-week')
            lastPos = 0 if lastPos == '--' else int(lastPos)

            weeks = int(getRowValue('weeks-on-chart'))

            # Get current rank
            rank = int(entry_soup.select_one('.chart-row__current-week').string.strip())

            change = lastPos - rank
            if lastPos == 0:
                # New entry
                if weeks > 1:
                    # If entry has been on charts before, it's a re-entry
                    change = "Re-Entry"
                else:
                    change = "New"
            elif change > 0:
                change = "+" + str(change)
            else:
                change = str(change)
            
            # Get spotify link for this track
            linkInfo = entry_soup.find('a', 'chart-row__player-link')
            spotifyLink = linkInfo.get('href').strip() if linkInfo else 'none'
            
            self.entries.append(
                ChartEntry(title, artist, peakPos,
                           lastPos, weeks, rank, change, spotifyLink))

        # Hot Shot Debut is the top-ranked new entry, or the first "New" entry
        # we find.
        for entry in self.entries:
            if entry.change == "New":
                entry.change = "Hot Shot Debut"
                break


def downloadHTML(url):
    """Downloads and returns the webpage with the given URL.
    Returns an empty string on failure.
    """
    assert url.startswith('http://')
    req = requests.get(url, headers=HEADERS)
    if req.status_code == 200:
        return req.text
    else:
        return ''
