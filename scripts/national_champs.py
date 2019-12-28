import codecs
import requests
import pandas as pd
from io import StringIO

import json
from tqdm import tqdm as tqdm
from datetime import datetime
import argparse

url_search = 'https://rating.chgk.info/api/tournaments.json/search?name={}'
url_tournament = 'https://rating.chgk.info/api/tournaments/{}/list'
url_tournament_info = 'https://rating.chgk.info/api/tournaments/{}/'
url_recaps = 'https://rating.chgk.info/api/tournaments/{idtournament}/recaps/{idteam}'
url_player = 'https://rating.chgk.info/api/players/{}'
url_team = 'https://rating.chgk.info/api/teams/{}'


def get_json(url):
    """
    Get json by url request to rating.chgk.info
    :param url: str, url request to API
    :return: dict, JSON response
    """
    response = requests.get(url).text
    response = json.load(StringIO(response))
    return response


def get_tournament_list(query):
    """
    Get a list of tuornaments by query
    :param query: str, search query to rating.chgk.info
    :return: pd.DataFrame, df of tournaments
    """
    response = get_json(url_search.format(query))
    return pd.DataFrame(response['items'])


def get_national_championships(countries):
    """
    Get all the national championchips for given list of countries
    :param countries: list, countries
    :return: pd.DataFrame, df of tournaments
    """
    ts = []
    for country in countries:
        query = 'чемпионат '+ country[:-1]
        t = get_tournament_list(query)
        t = t[t.name.apply(lambda x: x.split()[-1][1:-1] in (country[1:-1], country[1:]))]
        t = pd.DataFrame({'idtournament': t.idtournament, 'year': t.date_end.apply(lambda x: x[:4]), 'country': country})
        ts.append(t)
    return pd.concat(ts).reset_index()


def format_tournament_dates(iso_date_start, iso_date_end, fmt="%Y-%m-%d %H:%M:%S"):
    """
    Make ISO dates readable
    :param iso_date_start: start date in ISO
    :param iso_date_end: end date in ISO
    :param fmt: parsing format, default=%Y-%m-%d %H:%M:%S
    :return: formatted date
    """
    ds = datetime.strptime(iso_date_start, fmt)
    de = datetime.strptime(iso_date_end, fmt)
    # TODO date parser to human-readable dates
    date = de.strftime("%d.%m.%Y")
    if ds.day != de.day:
        date = '{}-{}'.format(ds.strftime("%d"), date)
    return date


def get_name(idplayer, fmt='ns'):
    """
    Get player full name by id
    :param idplayer: int, player id
    :param fmt: str, defines output by keys n='name', s='surname', p='patronymic'; e.g. default ns='name surname'
    :return: str, full name
    """
    fdict = dict(n='name', s='surname', p='patronymic')
    response = json.load(StringIO(requests.get(url_player.format(idplayer)).text))[0]
    return ' '.join([response[fdict[f]] for f in fmt])


def get_names(players):
    """
    Get full names for a list of players
    :param players: list, player ids
    :return: list, player full names
    """
    return [get_name(i) for i in tqdm(players)]


def get_winner_recaps(idtournament):
    """
    Get recaps of tournament winner by tournament id
    :param idtournament: int, tournament id
    :return: {team: (idteam, current_name, town),
              recaps: [(idplayer, surname name patronymic), ...]}
    """
    # Get tournament results
    teams = get_json(url_tournament.format(idtournament))
    # Get winner info
    winner = [t for t in teams if float(t['position']) < 2]
    if len(winner) > 1:
        # TODO proper logging
        # print('More than one winner in tournament', idtournament)
        pass
    try:
        winner = winner[0]
    except IndexError:
        # Tournament did not happen yet, no winners
        return {'team': None, 'recaps': None}
    idteam, winner = winner['idteam'], winner['current_name']
    town = get_json(url_team.format(idteam))[0]['town']
    # Get winner recaps
    winner_recaps = get_json(url_recaps.format(idtournament=idtournament, idteam=idteam))
    # Format recaps (idplayer, surname name patronymic (K?))
    winner_recaps = [(p['idplayer'], get_name(p['idplayer']) + (' (K)' if p['is_captain'] == '1' else '')) for p in
                     winner_recaps]

    return {'team': (idteam, winner, town), 'recaps': winner_recaps}


def get_tournament_header(idtournament):
    """
    Get basic tournament info
    :param idtournament: int, tournament id
    :return: tuple (idtournament:int, long_name:str, date:str, town:str)
    """
    tourn = get_json(url_tournament_info.format(idtournament))[0]
    date = format_tournament_dates(tourn['date_start'], tourn['date_end'])
    name = tourn['long_name'] if tourn['long_name'] else tourn['name']
    return tourn['idtournament'], name, date, tourn['town']


def format_player(player_tuple):
    """
    HTML-formatted player name
    :param player_tuple: tuple (int:idplayer, str:name), player data to format
    :return: str, player name with hyperlink to their rating page
    """
    return '<a href="https://rating.chgk.info/player/{}">{}</a>'.format(*player_tuple)


def format_team_recaps(team_recaps, prefix='Победитель '):
    """
    HTML-formatted recaps
    :param team_recaps: return of get_winner_recaps()
    :param prefix: text before formatting
    :return: str, team recaps with hyperlinks to rating pages
    """
    if team_recaps['team'] is None:
        return None
    head = '<p>{}<a href="https://rating.chgk.info/team/{}"><strong>{} ({})</strong> </a></p>'.format(
        prefix,
        *team_recaps['team'])
    ul = '\n'.join(['<li>' + format_player(pt) for pt in team_recaps['recaps']])
    ul = '<ul>{}</ul>'.format(ul)
    return '{}\n{}'.format(head, ul)


def format_tournament_header(tournament_tuple):
    """
    HTML-formatted tournament info
    :param tournament_tuple: return of get_tournament_header()
    :return: str, tournament header
    """
    return '<p><a href="https://rating.chgk.info/tournament/{}"><strong>{}</strong></a>: {}, {}</p>'.format(*tournament_tuple)


def format_tournament(idtournament):
    """
    HTML-formatted tournament info by id
    :param idtournament: tournament id
    :return: tournament header, tournament recaps
    """
    head = format_tournament_header(get_tournament_header(idtournament))
    body = format_team_recaps(get_winner_recaps(idtournament))
    return '{}\n{}'.format(head, body if body is not None else '')


def format_tournaments(idtournament_list):
    """
    HTML-formatted tournament info by id for a list of tournaments
    :param idtournament_list: list, tournament ids
    :return: tournament header, tournament recaps
    """
    tl = [format_tournament(idtournament) for idtournament in tqdm(idtournament_list, ascii=True)]
    return '\n'.join(tl)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Get info about national championship winners from rating.chgk.info')
    parser.add_argument('countries', nargs='+', help='List of countries to process')
    args = parser.parse_args()
    for country in args.countries:
        print(u'Process query "{}"...'.format(country))
        championships = get_national_championships([country])
        html = format_tournaments(championships.idtournament)
        with codecs.open(u'../data/national_champs/{}_long.html'.format(country), 'w', encoding="utf-8") as f:
            f.write(html)
    # print(championships.idtournament)
