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
    :return: list, dict of tournaments
    """
    response = get_json(url_search.format(query))
    return response['items']


def get_national_championships(countries, ascending=False):
    """
    Get all the national championchips for given list of countries
    :param countries: list, countries
    :param ascending: bool, sort tournaments
    :return: pd.DataFrame, df of tournaments
    """
    ts = []
    for country in countries:
        t = []
        queries = ['чемпионат {}'.format(country[:-1]), 'открытый чемпионат {}'.format(country[:-1])]
        for q in queries:
            t += get_tournament_list(q)
        t = pd.DataFrame(t)
        t = t[t.name.apply(lambda x: x.split()[-1][1:-1] in (country[1:-1], country[1:]))]
        t = pd.DataFrame({'idtournament': t.idtournament, 'year': t.date_end.apply(lambda x: x[:4]), 'country': country})
        ts.append(t)
    return pd.concat(ts).reset_index().sort_values(by='year', ascending=ascending)


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


def get_winner_recaps(idtournament, country):
    """
    Get recaps of tournament winner by tournament id
    :param idtournament: int, tournament id
    :param country: country to filter out foreign teams
    :return: {team: (idteam, current_name, town),
              recaps: [(idplayer, surname name patronymic), ...]}
    """
    # Get tournament results
    teams = sorted(get_json(url_tournament.format(idtournament)), key=lambda t: float(t['position'].replace(',', '.')))
    if len(teams) == 0:
        return {'team': None, 'recaps': None}

    # TODO check on multiple winners

    for team in teams:
        idteam, winner = team['idteam'], team['current_name']
        team_json = get_json(url_team.format(idteam))[0]
        town, team_country = team_json['town'], team_json['country_name']
        if team_country.lower() != country.lower():
            # TODO proper logging
            print(f'{winner} is a foreigner from {team_country}, not {country}')
            pass
        else:
            break
    # # Get winner info
    # winner = [t for t in teams if float(t['position']) < 2]
    # if len(winner) > 1:
    #     # TODO proper logging
    #     # print('More than one winner in tournament', idtournament)
    #     pass
    # try:
    #     winner = winner[0]
    # except IndexError:
    #     # Tournament did not happen yet, no winners
    #     return {'team': None, 'recaps': None}
    # idteam, winner = winner['idteam'], winner['current_name']
    # town = get_json(url_team.format(idteam))[0]['town']
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
    return tourn['idtournament'], name, date, tourn['town'] if tourn['town'] else ''


def format_player(player_tuple, add_link=False):
    """
    HTML-formatted player name
    :param player_tuple: tuple (int:idplayer, str:name), player data to format
    :param add_link: add hyperlink to rating.chgk.info
    :return: str, player name with hyperlink to their rating page
    """
    if add_link:
        return '<a href="https://rating.chgk.info/player/{}">{}</a>'.format(*player_tuple)
    else:
        return player_tuple[1]


def format_team_recaps(team_recaps, prefix='Победитель: ', add_link=False):
    """
    HTML-formatted recaps
    :param team_recaps: return of get_winner_recaps()
    :param prefix: text before formatting
    :param add_link: add hyperlink to rating.chgk.info
    :return: str, team recaps with hyperlinks to rating pages
    """
    if team_recaps['team'] is None:
        return None
    if add_link:
        head = '<p>{}<a href="https://rating.chgk.info/team/{}"><strong>{} ({})</strong> </a></p>'.format(
            prefix,
            *team_recaps['team'])

    else:
        head = '<p>{}<strong>{} ({})</strong></p>'.format(prefix, *team_recaps['team'][1:])
    ul = '\n'.join(['<li>' + format_player(pt, add_link=add_link) for pt in team_recaps['recaps']])
    ul = '<ul>{}</ul>'.format(ul)
    return '{}\n{}'.format(head, ul)


def format_tournament_header(tournament_tuple, add_link=False):
    """
    HTML-formatted tournament info
    :param tournament_tuple: return of get_tournament_header()
    :param add_link: add hyperlink to rating.chgk.info
    :return: str, tournament header
    """
    if add_link:
        return '<p><a href="https://rating.chgk.info/tournament/{}"><strong>{}</strong></a>: {}, {}</p>'.format(
            *tournament_tuple)
    else:
        return '<p><strong>{}</strong>: {}, {}</p>'.format(*tournament_tuple[1:])


def format_tournament(idtournament, country, add_link=False, add_tail=True):
    """
    HTML-formatted tournament info by id
    :param idtournament: tournament id
    :param country: country to filter out foreign teams
    :param add_link: add hyperlink to rating.chgk.info for team and players
    :param add_tail: add tail with hyperlink to results at rating.chgk.info
    :return: tournament header, tournament recaps
    """
    tournament_header = get_tournament_header(idtournament)
    head = format_tournament_header(tournament_header, add_link=add_link)
    body = format_team_recaps(get_winner_recaps(idtournament, country), add_link=add_link)
    tail = '<p>Результаты: <a href="https://rating.chgk.info/tournament/{}">на сайте рейтинга</a></p>'.format(
        tournament_header[0])

    entry = '{}\n{}'.format(head, body if body is not None else '')
    if add_tail:
        entry = '{}\n{}'.format(entry, tail)
    return entry


def format_tournaments(idtournament_list, *args, **kwargs):
    """
    HTML-formatted tournament info by id for a list of tournaments
    :param idtournament_list: list, tournament ids
    :param args, kwargs: see format_tournament()
    :return: tournament header, tournament recaps
    """
    tl = [format_tournament(idtournament, *args, **kwargs) for idtournament in tqdm(idtournament_list, ascii=True)]
    return '\n'.join(tl)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Get info about national championship winners from rating.chgk.info')
    parser.add_argument('countries', nargs='+', help='List of countries to process')
    parser.add_argument('-t', '--tail', action='store_true', default=False, help='Add tail with link to rating results')
    parser.add_argument('-l', '--link', action='store_true', default=False, help='Add hyperlinks for players and teams')
    parser.add_argument('-a', '--ascending', action='store_true', default=False, help='From old to new')
    args = parser.parse_args()

    for country in args.countries:
        print(u'Process query "{}"...'.format(country))
        championships = get_national_championships([country], ascending=args.ascending)
        html = format_tournaments(championships.idtournament, country, add_link=args.link, add_tail=args.tail)
        with codecs.open(u'./data/national_champs/{}_long.html'.format(country), 'w', encoding="utf-8") as f:
            f.write(html)
    # print(championships.idtournament)
