import numpy as np
import json
import os
import scipy as sp
import scipy.stats
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


def key_card(mtg_format=['standard']):
    return {str(index): card for card, index in card_key(mtg_format=mtg_format).items()}


#a higher (lower) norm makes the ranking more (less) favorable to popular cards
def matrix(mtg_format=['standard'], ignore_count=False, output=False, proportion=False, norm=30, data_fmt='%u'):
    tournament_path = DATA_REPO + 'tournament_data_' + '_'.join(mtg_format) + '.json'
    matrix_path = DATA_REPO + 'adjacency' + '_'.join([ignore_count*'ignore_count',
                                                      proportion*'proportion'] + mtg_format) + '.txt'
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
            try:
                record = (int(record.split('-')[0]), int(record.split('-')[1]))
            except AttributeError:
                continue
            for index in range(2):
                if not record[index]:
                    continue
                for i, card_id in enumerate(card_keys[index]):
                    for opp_card_id in card_keys[index-1]:
                        if ignore_count:
                            adjacency[card_id][opp_card_id] += record[index]
                        else:
                            adjacency[card_id][opp_card_id] += record[index]*card_counts[index][i]
    if proportion:
        data_fmt = '%.3f'
        for i in range(len(card_dict)):
            for j in range(len(card_dict)):
                if j <= i:
                    try:
                        adjacency[i][j] = (norm/2 + float(adjacency[i][j]))/(norm + adjacency[i][j] + adjacency[j][i])
                        adjacency[j][i] = 1 - adjacency[i][j]
                    except (ValueError, ZeroDivisionError):
                        adjacency[i][j], adjacency[j][i] = 0, 0
    if output:
        np.savetxt(matrix_path, adjacency, fmt=data_fmt)
    else:
        return adjacency


def mean_confidence_interval(data, confidence=0.95):
    a = 1.0*np.array(data)
    n = len(a)
    m, se = np.mean(a), scipy.stats.sem(a)
    h = se * sp.stats.t._ppf((1+confidence)/2., n-1)
    return m, m-h, m+h


def best_cards(mtg_format=['standard'], ignore_count=False, proportion=True, top_x=20):
    key_card_dict = key_card(mtg_format=mtg_format)
    card_matrix = matrix(mtg_format=mtg_format, ignore_count=ignore_count, proportion=proportion)
    #average values over rows and sort. We only want non-zero values.
    conf_ints = np.apply_along_axis(mean_confidence_interval, axis=1, arr=card_matrix)
    card_conf_ints = [(key_card_dict[str(card_index)], conf_int) for card_index, conf_int in enumerate(conf_ints)]
    #sort in descending order by mean
    sorted_conf_ints = sorted(card_conf_ints, key=lambda x: x[1][0], reverse=True)
    print(sorted_conf_ints)


if __name__ == '__main__':
    #print(best_cards(mtg_format=['limited'], ignore_count=True))
    print(best_cards(mtg_format=['standard'], ignore_count=True))