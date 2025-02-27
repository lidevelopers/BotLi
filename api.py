import json
from queue import Queue
from typing import Iterator

import requests
from tenacity import retry
from tenacity.retry import retry_if_exception_type

from api_challenge_response import API_Challenge_Reponse
from challenge_request import Challenge_Request
from enums import Decline_Reason, Perf_Type, Variant


class API:
    def __init__(self, token: str) -> None:
        self.session = requests.session()
        self.session.headers.update({'Authorization': f'Bearer {token}'})
        self.user = self.get_account()
        self.session.headers.update({'User-Agent': f'BotLi user:{self.user["username"]}'})

    @retry(retry=retry_if_exception_type(requests.ConnectionError))
    def abort_game(self, game_id: str) -> bool:
        try:
            response = self.session.post(f'https://lichess.org/api/bot/game/{game_id}/abort')
            response.raise_for_status()
            return True
        except requests.HTTPError as e:
            print(e)
            return False

    @retry(retry=retry_if_exception_type(requests.ConnectionError))
    def accept_challenge(self, challenge_id: str) -> bool:
        try:
            response = self.session.post(f'https://lichess.org/api/challenge/{challenge_id}/accept')
            response.raise_for_status()
            return True
        except requests.HTTPError as e:
            print(e)
            return False

    @retry(retry=retry_if_exception_type(requests.ConnectionError))
    def cancel_challenge(self, challenge_id: str) -> bool:
        try:
            response = self.session.post(f'https://lichess.org/api/challenge/{challenge_id}/cancel')
            response.raise_for_status()
            return True
        except requests.HTTPError as e:
            print(e)
            return False

    @retry(retry=retry_if_exception_type(requests.ConnectionError))
    def create_challenge(self, challenge_request: Challenge_Request, response_queue: Queue[API_Challenge_Reponse]) -> None:
        response = self.session.post(
            f'https://lichess.org/api/challenge/{challenge_request.opponent_username}',
            data={'rated': str(challenge_request.rated).lower(),
                  'clock.limit': challenge_request.initial_time, 'clock.increment': challenge_request.increment,
                  'color': challenge_request.color.value, 'variant': challenge_request.variant.value,
                  'keepAliveStream': 'true'},
            stream=True)

        if response.status_code == 429:
            response_queue.put(API_Challenge_Reponse(has_reached_rate_limit=True))
            return

        for line in filter(None, response.iter_lines()):
            data = json.loads(line)
            challenge_id = data.get('challenge', {'id': None}).get('id')
            was_accepted = data.get('done') == 'accepted'
            error = data.get('error')
            was_declined = data.get('done') == 'declined'
            response_queue.put(API_Challenge_Reponse(challenge_id, was_accepted, error, was_declined))

    @retry(retry=retry_if_exception_type(requests.ConnectionError))
    def decline_challenge(self, challenge_id: str, reason: Decline_Reason) -> bool:
        try:
            response = self.session.post(
                f'https://lichess.org/api/challenge/{challenge_id}/decline', data={'reason': reason.value})
            response.raise_for_status()
            return True
        except requests.HTTPError as e:
            print(e)
            return False

    def get_account(self) -> dict:
        response = self.session.get('https://lichess.org/api/account')
        return response.json()

    def get_chessdb_eval(self, fen: str, action: str, timeout: int) -> dict | None:
        try:
            response = self.session.get('http://www.chessdb.cn/cdb.php',
                                        params={'action': action, 'board': fen, 'json': 1},
                                        headers={'Authorization': None},
                                        timeout=timeout)
            response.raise_for_status()
            return response.json()
        except (requests.Timeout, requests.HTTPError, requests.ConnectionError) as e:
            print(e)

    def get_cloud_eval(self, fen: str, variant: Variant, timeout: int) -> dict | None:
        try:
            response = self.session.get('https://lichess.org/api/cloud-eval',
                                        params={'fen': fen, 'variant': variant.value}, timeout=timeout)
            return response.json()
        except (requests.Timeout, requests.ConnectionError) as e:
            print(e)

    def get_egtb(self, fen: str, variant: str, timeout: int) -> dict | None:
        try:
            response = self.session.get(
                f'https://tablebase.lichess.ovh/{variant}', params={'fen': fen},
                headers={'Authorization': None},
                timeout=timeout)
            response.raise_for_status()
            return response.json()
        except (requests.Timeout, requests.HTTPError, requests.ConnectionError) as e:
            print(e)

    def get_event_stream(self) -> Iterator:
        response = self.session.get('https://lichess.org/api/stream/event', stream=True)
        return response.iter_lines()

    def get_game_stream(self, game_id: str) -> Iterator:
        response = self.session.get(f'https://lichess.org/api/bot/game/stream/{game_id}', stream=True)
        return response.iter_lines()

    def get_online_bots_stream(self) -> Iterator:
        response = self.session.get('https://lichess.org/api/bot/online', stream=True)
        return response.iter_lines()

    def get_opening_explorer(self, username: str, fen: str, variant: Variant, color: str, timeout: int) -> dict | None:
        try:
            response = self.session.get('https://explorer.lichess.ovh/player',
                                        params={'player': username, 'variant': variant.value, 'fen': fen,
                                                'color': color, 'speeds': 'bullet,blitz,rapid,classical',
                                                'modes': 'rated', 'recentGames': 0},
                                        headers={'Authorization': None},
                                        stream=True, timeout=timeout)
            response.raise_for_status()
            *_, last_line = filter(None, response.iter_lines())
            return json.loads(last_line)
        except (requests.Timeout, requests.HTTPError, requests.ConnectionError) as e:
            print(e)

    @retry(retry=retry_if_exception_type(requests.ConnectionError))
    def get_perfomance(self, username: str, perf_type: Perf_Type) -> dict:
        response = self.session.get(f'https://lichess.org/api/user/{username}/perf/{perf_type.value}')
        return response.json()

    @retry(retry=retry_if_exception_type(requests.ConnectionError))
    def get_token_scopes(self, token: str) -> str:
        response = self.session.post('https://lichess.org/api/token/test', data=token)
        return response.json()[token]['scopes']

    @retry(retry=retry_if_exception_type(requests.ConnectionError))
    def resign_game(self, game_id: str) -> bool:
        try:
            response = self.session.post(f'https://lichess.org/api/bot/game/{game_id}/resign')
            response.raise_for_status()
            return True
        except requests.HTTPError as e:
            print(e)
            return False

    @retry(retry=retry_if_exception_type(requests.ConnectionError))
    def send_chat_message(self, game_id: str, room: str, text: str) -> bool:
        try:
            response = self.session.post(
                f'https://lichess.org/api/bot/game/{game_id}/chat', data={'room': room, 'text': text})
            response.raise_for_status()
            return True
        except requests.HTTPError as e:
            print(e)
            return False

    @retry(retry=retry_if_exception_type(requests.ConnectionError))
    def send_move(self, game_id: str, uci_move: str, offer_draw: bool) -> bool:
        try:
            response = self.session.post(
                f'https://lichess.org/api/bot/game/{game_id}/move/{uci_move}',
                params={'offeringDraw': str(offer_draw).lower()})
            response.raise_for_status()
            return True
        except requests.HTTPError as e:
            print(e)
            return False

    @retry(retry=retry_if_exception_type(requests.ConnectionError))
    def upgrade_account(self) -> bool:
        try:
            response = self.session.post('https://lichess.org/api/bot/account/upgrade')
            response.raise_for_status()
            return True
        except requests.HTTPError as e:
            print(e)
            return False
