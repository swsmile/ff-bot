#!/usr/bin/python3
import time
import logging
import requests
import json
import datetime

import threading
from enum import Enum, unique

INIT_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOlwvXC9hcGktbW9iaWxlLmNpcmN1aXRocS5jb21cL2FwaVwvdjFcL2F1dGhcL3Rva2VuXC9yZWZyZXNoIiwiaWF0IjoxNTk2MzgwNTMzLCJleHAiOjE1OTc4NDE4MzIsIm5iZiI6MTU5NjYzMjIzMiwianRpIjoiMENHbG81dmhTVkhUQjlRbSIsInN1YiI6OTAxNzYsInBydiI6IjIzYmQ1Yzg5NDlmNjAwYWRiMzllNzAxYzQwMDg3MmRiN2E1OTc2ZjcifQ.PqktIiMocQQvUKDArDLweIfyfw_rFCOKRej-wfncfiI"
MY_TOKEN = INIT_TOKEN
WANT_REFRESH_TOKEN = True
FREQUENCY_TO_CHECK_CLASS_AVAILABILITY = 1  # 1 second
FREQUENCY_TO_BOOK = 0.3  # 1 second

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()


@unique
class ClubEnum(Enum):
	Clementi = 0  # Sun的value被设定为0


class GymClass:
	class_id = 0
	name = ""
	start_time = datetime.datetime.now()
	end_time = datetime.datetime.now()
	club = ClubEnum.Clementi
	capacity = 0

	def __str__(self):
		return "GymClass - name: {}, class_id: {}, start_time: {}, end_time: {}, club: {}".format(self.name,
																								  self.class_id,
																								  self.start_time,
																								  self.end_time,
																								  self.club)


def send_http_post(url):
	headers = {
		'Host': 'api-mobile.circuithq.com',
		'content-type': 'application/json',
		'accept': '*/*',
		'authorization': 'Bearer ' + MY_TOKEN,
		'user-country-code': 'sg',
		'accept-language': 'en-CN;q=1.0, zh-Hans-CN;q=0.9',
		'user-locale': 'cn',
		'user-agent': 'Fitness First Asia/1.10 (com.EvolutionWellness.App.FitnessFirst; build:66; iOS 13.6.0) Alamofire/4.8.2',
		'user-brand-code': 'ff',
	}
	response = requests.post(url, headers=headers,
							 verify=False)
	return response


def find_date_list_needing_to_book():
	date_needed_to_book_list = []
	booked_classes = get_booked_classes()
	now = datetime.datetime.now()

	need_book_today = True
	need_book_tomorrow = True
	# need_book_2_days_later = True
	for c in booked_classes:
		if c.start_time.day == now.day:
			need_book_today = False
		if c.start_time.day == (now + datetime.timedelta(days=1)).day:
			need_book_tomorrow = False

	if need_book_today:
		date_needed_to_book_list.append(now)
	if need_book_tomorrow:
		date_needed_to_book_list.append((now + datetime.timedelta(days=1)))

	date_needed_to_book_list.append((now + datetime.timedelta(days=2)))

	return date_needed_to_book_list


def refresh_token():
	if not WANT_REFRESH_TOKEN:
		# TOKEN = INIT_TOKEN
		return True

	response = send_http_post('https://api-mobile.circuithq.com/api/v1/auth/token/refresh')
	if response.status_code == 401:
		print("invali token provided: ", MY_TOKEN)
		print("error msg: ", response.text)
		return False

	# Unknown error
	if not response.ok:
		print(response.status_code)
		print(response.text)
		return False

	data = json.loads(response.text)
	token = data["data"]["token"]
	TOKEN = token
	print("We have a new token: " + token)

	return True


def get_club_id_by_club_enum(e):
	if e == ClubEnum.Clementi:
		# 321 Clementi: 19
		return 19
	else:
		return 19


def get_club_enum_by_club_id(club_id):
	club_id = int(club_id)
	if club_id == 19:
		return ClubEnum.Clementi
	else:
		return ClubEnum.Clementi


def parse_classes(classes_dict):
	class_to_book = []
	for c in classes_dict:
		class_id = c["classId"]
		class_name = c["name"]
		# "timeStart": 1595046600,
		timeStart = c["timeStart"]
		# "timeEnd": 1595052000,
		timeEnd = c["timeEnd"]
		# capacity 指定可以订的slot
		capacity = c["capacity"]

		club_id = c["club"]["clubId"]

		# "name": "Gym Floor."
		# 这样的不能订："name": "Personal Training",
		# TODO Filter
		# class_name.find("Gym Floor") != -1
		if class_name.find("Personal Training") == -1 and club_id == get_club_id_by_club_enum(ClubEnum.Clementi):
			gym_class = GymClass()
			gym_class.class_id = class_id
			gym_class.name = class_name

			gym_class.start_time = datetime.datetime.fromtimestamp(int(timeStart))
			gym_class.end_time = datetime.datetime.fromtimestamp(int(timeEnd))
			gym_class.club = get_club_enum_by_club_id(club_id)
			gym_class.capacity = capacity

			class_to_book.append(gym_class)

	return class_to_book


# Didn't find any available class
# print("Didn't find any available class")


def book_class(c):
	# without this Cookie is ok
	# cookies = {
	# 	'ARRAffinity': '94172f5487d231c2d0c7ffe567b886259eb44ddbfd8f88adc109ab9b026ea441',
	# }
	cookies = {}
	response = send_http_post('https://api-mobile.circuithq.com/api/v1/auth/token/refresh')
	headers = {
		'Host': 'api-mobile.circuithq.com',
		'content-type': 'application/json',
		'accept': '*/*',
		'user-country-code': 'sg',
		'user-locale': 'cn',
		'accept-language': 'en-CN;q=1.0',
		'user-agent': 'Fitness First Asia/1.10 (com.EvolutionWellness.App.FitnessFirst; build:66; iOS 13.3.0) Alamofire/4.8.2',
		'user-brand-code': 'ff',
		'authorization': 'Bearer ' + MY_TOKEN,
	}

	data = '{"class_id": ' + str(c.class_id) + '}'

	while True:
		response = requests.post('https://api-mobile.circuithq.com/api/v2/class/book', headers=headers, cookies=cookies,
								 data=data, verify=False)
		response_data = json.loads(response.text)
		if response.status_code == 200:
			print("we make it")
			# TODO send to MM
			booked_class = data["data"]
			return True

		if response.status_code == 400:
			if "error" in response_data and response_data["error"] and "code" in response_data["error"] and \
					response_data["error"]["code"] == 10 and "messages" in response_data["error"] and len(
				response_data["error"]["messages"]) > 0:
				msg = response_data["error"]["messages"][0]["message"]

				if msg == "booking_errors_too_late":
					# logging.info(
					# 	"we are too late to book or we have booked it, so give up, class_id: %s, start_time: %s, name: %s",
					# 	c.class_id, c.start_time.strftime("%Y-%m-%d %H:%M:%S"), c.name)
					return False
				elif msg == "booking_errors_fully_booked":
					logging.info(
						"[retry] try to book (class_id: %s), but fail due to full capacity...|start_time: %s, name: %s",
						c.class_id, c.start_time.strftime("%Y-%m-%d %H:%M:%S"), c.name)
					time.sleep(FREQUENCY_TO_BOOK)
					continue
				elif msg == "booking_errors_too_soon":
					logging.info(
						"[retry] try to book (class_id: %s), but fail due to be too early...|start_time: %s, name: %s",
						c.class_id, c.start_time.strftime("%Y-%m-%d %H:%M:%S"), c.name)

					# TODO
					time.sleep(FREQUENCY_TO_BOOK)
					continue
				elif msg == "booking_errors_overlap":
					# logging.info(
					# 	"booked already...|class_id: %s, start_time: %s, name: %s",
					# 	c.class_id, c.start_time.strftime("%Y-%m-%d %H:%M:%S"), c.name)
					return False

		logging.warning("Unknown error|status_code: %s, response: %s", response.status_code, response.text)
		return False


def get_booked_classes():
	booked_classes = []
	headers = {
		'Host': 'api-mobile.circuithq.com',
		'accept': '*/*',
		'content-type': 'application/json',
		'user-locale': 'cn',
		'authorization': 'Bearer ' + MY_TOKEN,
		'user-brand-code': 'ff',
		'user-agent': 'Fitness First Asia/1.12 (com.EvolutionWellness.App.FitnessFirst; build:68; iOS 13.6.0) Alamofire/4.8.2',
		'accept-language': 'en-CN;q=1.0',
		'user-country-code': 'sg',
	}

	params = (
		('page', '1'),
		('pageSize', '25'),
	)

	response = requests.get('https://api-mobile.circuithq.com/api/v2/booking/upcoming', headers=headers, params=params,
							verify=False)
	if response.status_code == 401:
		print("invalid initialized token provided: ", MY_TOKEN)
		print("error msg: ", response.text)
		return booked_classes

	# Unknown error
	if not response.ok:
		print(response.status_code)
		print(response.text)
		return booked_classes

	data = json.loads(response.text)
	booked_classes_dict = data["data"]

	for c_dict in booked_classes_dict:
		c = GymClass()
		c.class_id = c_dict["classId"]
		c.name = c_dict["name"]
		c.start_time = datetime.datetime.fromtimestamp(int(c_dict["timeStart"]))
		c.end_time = datetime.datetime.fromtimestamp(int(c_dict["timeStart"]))
		c.club = get_club_enum_by_club_id(c_dict["club"]["clubId"])
		booked_classes.append(c)
		logging.info("booked_class: %s", c)

	return booked_classes


# Return class_ids_to_book
def query_class_for_a_day(date_for_query):
	headers = {
		'Host': 'api-mobile.circuithq.com',
		'accept': '*/*',
		'content-type': 'application/json',
		'user-locale': 'cn',
		'authorization': 'Bearer ' + INIT_TOKEN,
		'accept-language': 'en-CN;q=1.0, zh-Hans-CN;q=0.9',
		'user-brand-code': 'ff',
		'user-agent': 'Fitness First Asia/1.10 (com.EvolutionWellness.App.FitnessFirst; build:66; iOS 13.6.0) Alamofire/4.8.2',
		'user-country-code': 'sg',
	}

	start_time_for_book_query = date_for_query
	start_time_for_book_query = date_for_query.replace(hour=20)
	start_time_for_book_query = start_time_for_book_query.replace(minute=1)

	end_time_for_book_query = date_for_query
	end_time_for_book_query = date_for_query.replace(hour=22)
	end_time_for_book_query = end_time_for_book_query.replace(minute=30)
	params = (
		('pageSize', '1000'),

		('clubId', str(get_club_id_by_club_enum(ClubEnum.Clementi))),
		('maxPrice', '150.0'),
		('pageNumber', '1'),
		('minPrice', '0.0'),
		# SG time
		('fromDate', str(int(start_time_for_book_query.timestamp()))),
		# SG time
		('toDate', str(int(end_time_for_book_query.timestamp()))),
	)

	logging.info("got class info already, start_time_for_book_query: %s, end_time_for_book_query: %s, club: %s",
				 start_time_for_book_query.strftime('%Y-%m-%d %H:%M:%S'),
				 end_time_for_book_query.strftime('%Y-%m-%d %H:%M:%S'), ClubEnum.Clementi)

	while True:
		response = requests.get('https://api-mobile.circuithq.com/api/v2/class/search/', headers=headers, params=params,
								verify=False)
		data = json.loads(response.text)

		if response.status_code == 401:  # We need to refresh token
			#  {"error":{"code":10,"messages":[{"message":"errors_token_blacklisted"}]}}
			if refresh_token():
				continue

		if response.status_code == 200 and len(data["data"]) > 1:
			classes_dict = data["data"]
			return parse_classes(classes_dict)
		# time.sleep(FREQUENCY_TO_CHECK_CLASS_AVAILABILITY)

		# Cannot continue, because of unknown error
		print(response.status_code)
		print(response.text)
		break


def find_classes_to_book(date_needed_to_book_list):
	classes_to_book = []
	for d in date_needed_to_book_list:
		classes_to_book_per_day = query_class_for_a_day(d)
		classes_to_book.extend(classes_to_book_per_day)
	return classes_to_book


def book_classes(classes_to_book):
	for c in classes_to_book:
		t = threading.Thread(target=book_class, args=(c,))
		t.start()


def init():
	logging.basicConfig(format='%(asctime)s|%(levelname)s|%(filename)s %(funcName)s %(lineno)s|%(message)s',
						level=logging.INFO)


def start():
	date_needed_to_book_list = find_date_list_needing_to_book()
	classes_to_book = find_classes_to_book(date_needed_to_book_list)
	book_classes(classes_to_book)


init()
start()
