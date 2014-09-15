import itertools
import json
from lxml import html
import os
import requests
from requests.exceptions import Timeout, ConnectionError
import math

DATA_REPO = '/'.join(os.path.dirname(os.path.realpath(__file__)).split('/')[:-1]) + '/data/'
URL = 'http://www.mtggoldfish.com/tournament/'
ML_URL = 'http://www.magic-league.com/'


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


def ml_tournament_ids(mtg_format=['standard'], output=True, verbose=True):
    id_list = list()
    add_ids = id_list.extend
    if not os.path.isdir(DATA_REPO):
        os.makedirs(DATA_REPO)
    for i in range(0, 5000, 50):
        link = ML_URL + 'tourney_list.php?start=' + str(i)
        try:
            page = html.fromstring(requests.get(link, timeout=10).text)
        except (IOError, TypeError, Timeout):
            print('request error')
            continue
        #only stores ids of tournaments that match the specified mtg_format(s)
        ids = [b.text for a in page.xpath('/html/body/table//tr[2]/td[2]/div[2]/table//tr')
               for b in a.xpath('td/a[@href]') if a.xpath('td[3]')[0].text.lower() in mtg_format]
        add_ids(ids)
        if verbose:
            print(ids)
            print(i)
    if output:
        write_path = DATA_REPO + 'tournament_ids_' + '_'.join(mtg_format) + '.json'
        with open(write_path, 'w') as writefile:
            json.dump(id_list, writefile, indent=4, sort_keys=True, separators=(',', ': '))
    else:
        return id_list


def ml_tournament_player_data(tournament_id):
    """
    Includes player names, player decks, and player records for the tournament in question.
    """
    link = ML_URL + 'tournament/info.php?id=' + str(tournament_id) + '&view=decks'
    try:
        page = html.fromstring(requests.get(link, timeout=10).text)
    except (IOError, TypeError, Timeout):
        print('request error')
        return
    players_records = [(a.text.split('|')[0].split(':')[-1].strip(' '),
                        a.text.split('|')[-1].split(':')[-1].strip(' '))
                       for a in page.xpath('/html/body/table//tr[2]/td[2]/div[2]//table[3]//tr/td/table//tr[2]/td')]
    #list of lists of each players decklist
    decks = [a.xpath('text()') for a in page.xpath('//td[@class="MD"]')]
    decks = [[card.strip('\n\t\t\t') for card in decks[i] + decks[i+1]] for i in range(0, len(decks), 2)]
    players, records = zip(*players_records)
    return players, records, decks


def ml_tournament_matchups(tournament_id, round_count):
    links = (ML_URL + 'tournament/info.php?id=' + str(tournament_id) + '&round=' + str(i)
             for i in range(1, round_count + 1))
    matchups = list()
    for link in links:
        try:
            page = html.fromstring(requests.get(link, timeout=10).text)
        except (IOError, TypeError, Timeout):
            print('request error')
            return
        round_matchups = [(a.xpath('td')[1].text.split(' ')[-1].strip('()'),
                           a.xpath('td')[3].text.split(' ')[-1].strip('()'),
                           a.xpath('td')[4].text) for a in page.xpath('//table[3]//tr') if a.xpath('td')]
        matchups.extend(round_matchups)
    return matchups


def ml_tournament(mtg_format=['standard'], output=True, verbose=True):
    path = DATA_REPO + 'tournament_ids_' + '_'.join(mtg_format) + '.json'
    if not os.path.isfile(path):
        ml_tournament_ids(mtg_format=mtg_format)
    with open(path) as file:
        ids = json.load(file)
    tournament_data = list()
    add_data = tournament_data.append
    for id in ids:
        link = ML_URL + 'tournament/info.php?id=' + str(id)
        try:
            page = html.fromstring(requests.get(link, timeout=10).text)
        except (IOError, TypeError, Timeout):
            print('request error')
            continue
        players, records, decks = ml_tournament_player_data(id)
        #make sure all the data is present
        if not any(players):
            continue
        round_count = math.ceil(math.log2(len(players)))

        date = page.xpath('/html/body/table//tr[2]/td[2]/div[2]//table[2]//tr[2]/td[2]')[0].text.split(' ')[1]

        matchups = ml_tournament_matchups(id, round_count=round_count)
        data = dict(id=id, date=date, matchups=matchups,
                    entries=[dict(player=players[i], deck=decks[i], record=records[i]) for i in range(len(players))])
        add_data(data)
        if verbose:
            print(data)
    if output:
        write_path = DATA_REPO + 'tournament_data_' + '_'.join(mtg_format) + '.json'
        with open(write_path, 'w') as writefile:
            json.dump(tournament_data, writefile, indent=4, sort_keys=True, separators=(',', ': '))
    else:
        return tournament_data

if __name__ == "__main__":
    ml_tournament()