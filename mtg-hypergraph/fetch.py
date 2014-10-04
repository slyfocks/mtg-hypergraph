from collections import defaultdict
import itertools
import json
from lxml import html
import os
import requests
from requests.exceptions import Timeout, ConnectionError
import math
import numpy as np

DATA_REPO = '/'.join(os.path.dirname(os.path.realpath(__file__)).split('/')[:-1]) + '/data/'
URL = 'http://www.mtggoldfish.com/tournament/'
ML_URL = 'http://www.magic-league.com/'
SCG_URL = 'http://sales.starcitygames.com/deckdatabase/deckshow.php?&t%5BC1%5D=1'


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


def ml_tournament_ids(mtg_format=['constructed', 'limited'],
                      exclude=['modern', 'legacy', 'aq/aq/aq/aq/aq/aq sealed', '2e/2e/2e/2e/2e/2e sealed'],
                      output=False, verbose=True):
    id_list = list()
    add_ids = id_list.extend
    if not os.path.isdir(DATA_REPO):
        os.makedirs(DATA_REPO)
    for i in range(0, 1):
        link = ML_URL + 'tourney_list.php?start=' + str(i)
        try:
            page = html.fromstring(requests.get(link, timeout=10).text)
        except (IOError, TypeError, Timeout):
            print('request error')
            continue
        #only stores ids of tournaments that match the specified mtg_format(s)
        ids = [b.text for a in page.xpath('/html/body/table//tr[2]/td[2]/div[2]/table//tr')
               for b in a.xpath('td/a[@href]') if a.xpath('td[4]')[0].text.lower() in mtg_format
               and a.xpath('td[3]')[0].text.lower() not in exclude]
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
    try:
        players, records = zip(*players_records)
    except ValueError:
        return
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


def ml_tournament(mtg_format=['constructed', 'limited'], output=True, verbose=True):
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
        try:
            players, records, decks = ml_tournament_player_data(id)
        except TypeError:
            continue
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


def file_gen(path, *exts):
    """
    lists files with the given extensions
    """
    return (os.path.join(root, file) for root, dirs, files in os.walk(path)
            for file in files if any(file.endswith(ext) for ext in exts))


def scg_deck_data(path=DATA_REPO + 'scg_decks/', output=True, verbose=True):
    deck_files = file_gen(path, 'Deck.html')
    decks = list()
    add_deck = decks.append
    for deck_file in deck_files:
        with open(deck_file) as file:
            page = html.fromstring(file.read())
        deck_name = page.xpath('//*[@id="article_content"]/div/div[1]/div[1]/header[1]/a')[0].text
        if verbose:
            print(deck_name)
        player_name = page.xpath('//*[@id="article_content"]/div/div[1]/div[1]/header[2]/a')[0].text
        #scg has weird formatting, hence the extended space in the split.
        rank = page.xpath('//*[@id="article_content"]/div//div[1]/header[3]')[0].text.split('			')[1][:-2]
        tournament = page.xpath('//*[@id="article_content"]/div//div[1]/header[3]/a')[0].text
        date = page.xpath('//*[@id="article_content"]/div/div[1]/div[1]/header[3]/text()[2]')[0].split(' ')[-1]
        deck_types = [(a.text.replace('(', '').replace(')', '').split(' ')[0],
                      int(a.text.replace('(', '').replace(')', '').split(' ')[1]))
                      for a in page.xpath('//*[@id="article_content"]/div/div[3]/div/h3')]
        cards = [(a.xpath('a')[0].text, int(a.text)) for a in page.xpath('//ul[@rel]/li')]
        deck_data = dict(name=deck_name, player=player_name, rank=rank, event=tournament, date=date,
                         card=dict(types=deck_types, names=cards))
        add_deck(deck_data)
    if output:
        write_path = DATA_REPO + 'scg9272814.json'
        with open(write_path, 'w') as writefile:
            json.dump(decks, writefile, indent=4, sort_keys=True, separators=(',', ': '))
    else:
        return decks


def scg_card_data(deck_data=DATA_REPO + 'scg9272814.json', min_plays=20, card_combo=False, output=False):
    card_data = defaultdict(list)
    with open(deck_data) as file:
        data = json.load(file)
    for deck in data:
        if card_combo:
            for card_group in itertools.combinations(deck['card']['names'], r=card_combo):
                #get card names and join them with semi-colon
                card_name = '; '.join([card[0] for card in card_group])
                card_count = sum([card[1] for card in card_group])
                #appends x instances of the rank of the deck, where x is the quantity of the card in question
                card_data[card_name] += card_count*[int(deck['rank'])]
        else:
            for card in deck['card']['names']:
                card_data[card[0]] += card[1]*[int(deck['rank'])]

    for card in card_data:
        card_data[card] = (np.mean(card_data[card]), np.std(card_data[card]), len(card_data[card]))

    #only want cards that appear min_plays or more times
    card_data = [item for item in card_data.items() if item[1][2] >= min_plays]

    if output:
        write_path = output
        with open(write_path, 'w') as writefile:
            json.dump(card_data, writefile, indent=4, separators=(',', ': '))
    else:
        return card_data


#sort_key can be name, appearances, avg_rank, or std_dev_rank
def scg_sorted(deck_data_path, sort_key='appearances', reverse=True, output=True):
    with open(deck_data_path) as file:
        data = json.load(file)

    if sort_key == 'name':
        return sorted(data, key=lambda x: x[0], reverse=reverse)
    elif sort_key == 'avg_rank':
        k = 0
    elif sort_key == 'std_dev_rank':
        k = 1
    else:
        k = 2

    sorted_data = sorted(data, key=lambda x: x[1][k], reverse=reverse)

    if output:
        write_path = deck_data_path.split('.')[0] + sort_key + '_sorted.json'
        with open(write_path, 'w') as writefile:
            json.dump(sorted_data, writefile, indent=4, separators=(',', ': '))
    else:
        return sorted_data


if __name__ == "__main__":
    ml_tournament_ids(output=True)
    ml_tournament()
    #scg_card_data(card_combo=4, output=DATA_REPO + 'scg9272814data4combo.json')
    #scg_sorted(DATA_REPO + 'scg9272814data4combo.json', sort_key='avg_rank', reverse=False)