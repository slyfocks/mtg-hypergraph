import itertools
import json
from lxml import html
import os
import requests
from requests.exceptions import Timeout, ConnectionError

DATA_REPO = '/'.join(os.path.dirname(os.path.realpath(__file__)).split('/')[:-1]) + '/data/'
URL = 'http://www.mtggoldfish.com/tournament/'


def tournaments(output=DATA_REPO + 'tournaments.json', verbose=True):
    tourney_list = list()
    add_tourney = tourney_list.append
    if not os.path.isdir(DATA_REPO):
        os.makedirs(DATA_REPO)
    for i in itertools.count(1):
        link = URL + str(i)
        try:
            page = html.fromstring(requests.get(link, timeout=10).text)
        except (IOError, TypeError, Timeout):
            print('request error')
            continue
        try:
            t_format = page.xpath('/html/body/div/p')[0].text.strip('\n').split(':')[1]
        except IndexError:
            #If there is no colon, we have run out of tournaments IDs
            break
        try:
            date = page.xpath('/html/body/div[2]/p/text()[2]')[0].strip('\n').split(':')[1]
        except IndexError:
            continue
        name = page.xpath('/html/body/div[2]/h2')[0].text.strip('\n')
        deck_stats = [b for a in page.xpath('/html/body//div/table//tr') for b in a.xpath('td')]
        elements = list(zip([element.text for element in deck_stats[0::5]],
                            [element.text for element in deck_stats[1::5]],
                            [element.xpath('a[@href]')[0].attrib['href'] for element in deck_stats[2::5] if element]))
        elements = filter(lambda x: x[0] and x[1] and x[2] and x[0].isnumeric()
                          and x[1].isnumeric() and x[2].split('/')[-1].isnumeric(), elements)
        decks = [dict(wins=deck[0], losses=deck[1], id=deck[2].split('/')[-1]) for deck in elements]
        tourney_data = dict(decks=decks, name=name, date=date, format=t_format, id=str(i))
        if verbose:
            print(tourney_data)
        add_tourney(tourney_data)
    with open(output, 'w') as writefile:
        json.dump(tourney_list, writefile, indent=4, sort_keys=True, separators=(',', ': '))


tournaments()