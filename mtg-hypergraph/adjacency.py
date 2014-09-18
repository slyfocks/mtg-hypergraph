import numpy as np
import json
import os
from fetch import ml_tournament

DATA_REPO = '/'.join(os.path.dirname(os.path.realpath(__file__)).split('/')[:-1]) + '/data/'


def card_key(mtg_format=['standard'], output=False):
    data_path = DATA_REPO + 'tournament_data_' + '_'.join(mtg_format) + '.json'
    key_path = DATA_REPO + 'card_key_' + '_'.join(mtg_format) + '.json'
    if os.path.isfile(key_path) and not output:
        with open(key_path) as key_file:
            card_dict = json.load(key_file)
            return card_dict
    if not os.path.isfile(data_path):
        ml_tournament(mtg_format=mtg_format)
    with open(data_path) as file:
        data = json.load(file)
    card_set = set(' '.join(card.split(' ')[1:]) for tournament in data
                   for entry in tournament['entries'] for card in entry['deck'])
    card_dict = {card: index for index,card in enumerate(card_set)}
    if output:
        with open(key_path, 'w') as writefile:
            json.dump(card_dict, writefile, indent=4, sort_keys=True, separators=(',', ': '))
    else:
        return card_dict


def matrix(mtg_format=['standard']):
    tournament_path = DATA_REPO + 'tournament_data_' + '_'.join(mtg_format) + '.json'
    with open(tournament_path) as file:
        t_data = json.load(file)
    card_dict = card_key(mtg_format=mtg_format)
    adjacency = np.zeros((len(card_dict), len(card_dict)))
    for tournament in t_data:
        for matchup in tournament['matchups']:
            if "Bye" in matchup:
                continue
            *players, record = matchup
            decks = [entry['deck'] for player in players
                     for entry in tournament['entries']
                     if entry['player'] == player]
            card_keys = [[card_dict[' '.join(card.split(' ')[1:])] for card in deck] for deck in decks]
            card_counts = [[int(card.split(' ')[0]) for card in deck] for deck in decks]
            if len(card_keys) + len(card_counts) != 4:
                continue
            record = (int(record.split('-')[0]), int(record.split('-')[1]))
            for index in range(2):
                if not record[index]:
                    continue
                for i, card_id in enumerate(card_keys[index]):
                    for opp_card_id in card_keys[index-1]:
                        adjacency[card_id][opp_card_id] += card_counts[index][i]
    return adjacency



if __name__ == '__main__':
    print(matrix())