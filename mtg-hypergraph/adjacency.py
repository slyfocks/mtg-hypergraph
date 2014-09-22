import numpy as np
import json
import os
import networkx as nx
import matplotlib
matplotlib.use('Qt4Agg')
import matplotlib.pyplot as plt
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
def matrix(mtg_format=['standard'], ignore_count=False, output=False, proportion=False, norm=0.1, data_fmt='%u'):
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


def best_cards(mtg_format=['standard'], ignore_count=False, display_names=True,
               proportion=True, verbose=True, top_x=20):
    key_card_dict = key_card(mtg_format=mtg_format)
    card_matrix = matrix(mtg_format=mtg_format, ignore_count=ignore_count, proportion=proportion)
    #average values over rows and sort. We only want non-zero values.
    conf_ints = np.apply_along_axis(mean_confidence_interval, axis=1, arr=card_matrix)
    if display_names:
        card_conf_ints = [(key_card_dict[str(card_index)], conf_int) for card_index, conf_int in enumerate(conf_ints)]
    else:
        card_conf_ints = [(card_index, conf_int) for card_index, conf_int in enumerate(conf_ints)]
    #sort in descending order by mean
    sorted_conf_ints = sorted(card_conf_ints, key=lambda x: x[1][0], reverse=True)[:top_x]
    if verbose:
        print(sorted_conf_ints)
    return sorted_conf_ints


def best_cards_against(card_name, mtg_format=['standard'], top_x=30):
    card_to_key = card_key(mtg_format=mtg_format)
    key_to_card = key_card(mtg_format=mtg_format)
    card_matrix = matrix(mtg_format=['standard'], ignore_count=True)
    card_id = card_to_key[card_name]
    success_loss_array = [(index, [1]*card_matrix[index, card_id] + [0]*card_matrix[card_id, index])
                          for index in range(len(card_matrix[card_id]))
                          if card_matrix[card_id, index] + card_matrix[index, card_id]]
    #creates 95% confidence intervals and filters out (1.0, 1.0, 1.0) results
    conf_ints = [(key_to_card[str(matchup[0])], mean_confidence_interval(matchup[1]))
                 for matchup in success_loss_array if not all(int_val == 1.0 for int_val in matchup[1])]
    sorted_conf_ints = sorted(conf_ints, key=lambda x: x[1][1], reverse=True)[:top_x]
    print(sorted_conf_ints)


def digraph_best_cards(mtg_format=['standard'], top_x=2):
    card_matrix = matrix(mtg_format=mtg_format, ignore_count=True)
    success_loss_array = [[(i, j, [1]*card_matrix[i, j] + [0]*card_matrix[j, i]) for j in range(len(card_matrix))]
                          for i in range(len(card_matrix))]
    conf_ints = [sorted([(matchup[0], matchup[1], mean_confidence_interval(matchup[2])[1]) for matchup in row
                 if not all(int_val == 1.0 for int_val in matchup[2])], key=lambda x: x[2], reverse=True)[:top_x]
                 for row in success_loss_array]
    top_vals = [top_val for top_list in conf_ints for top_val in top_list if top_val[2] > 0.0]
    print(top_vals)
    DG = nx.DiGraph()
    DG.add_weighted_edges_from(top_vals)
    nx.draw(DG)
    plt.show()


#TODO: Create matrix out of top_x cards to reduce graphics/processing load

if __name__ == '__main__':
    import pylab as P
    import matplotlib.cm as cm

    def _blob(x, y, area, color):
        """
        Draws a square-shaped blob with the given area (< 1) at
        the given coordinates.
        """
        hs = np.sqrt(area) / 2
        xcorners = np.array([x - hs, x + hs, x + hs, x - hs])
        ycorners = np.array([y - hs, y - hs, y + hs, y + hs])
        P.fill(xcorners, ycorners, color=color)
    key_card_dict = key_card(mtg_format=['standard'])
    cards = [entry[0] for entry in best_cards(ignore_count=True, display_names=False, top_x=50)]
    names = [key_card_dict[str(card)] for card in cards]


    def hinton(W, max_weight=None, names=names):
        """
        Draws a Hinton diagram for visualizing a weight matrix.
        Temporarily disables matplotlib interactive mode if it is on,
        otherwise this takes forever.
        """
        reenable = False
        if P.isinteractive():
            P.ioff()
        P.clf()
        height, width = W.shape
        if not max_weight:
            max_weight = 2**np.ceil(np.log(np.max(np.abs(W)))/np.log(2))

        P.fill(np.array([0, width, width, 0]), np.array([0, 0, height, height]), 'gray')
        P.axis('off')
        P.axis('equal')
        cmap = plt.get_cmap('RdYlGn')
        for x in range(width):
            if names:
                plt.text(-0.5, x, names[x], fontsize=12, ha='right', va='bottom')
                plt.text(x, height+0.5, names[height-x-1], fontsize=12, va='bottom', rotation='vertical', ha='left')
            for y in range(height):
                _x = x+1
                _y = y+1
                w = W[y, x]
                if w > 0:
                    _blob(_x - 0.5, height - _y + 0.5, min(1, w/max_weight), color=cmap(w/max_weight))
                elif w < 0:
                    _blob(_x - 0.5, height - _y + 0.5, min(1, -w/max_weight), 'black')
        if reenable:
            P.ion()
        P.show()
    print(names)
    card_matrix = matrix(mtg_format=['standard'], ignore_count=True, proportion=True)
    card_matrix = card_matrix[:, cards][cards]
    print(card_matrix)
    hinton(card_matrix)