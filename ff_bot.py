#!/usr/bin/python3
import time
import logging
import requests
import json
import datetime

import threading
from enum import Enum, unique


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


class Mybot:
	INIT_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOlwvXC9hcGktbW9iaWxlLmNpcmN1aXRocS5jb21cL2FwaVwvdjFcL2F1dGhcL3Rva2VuXC9yZWZyZXNoIiwiaWF0IjoxNTk2MzgwNTMzLCJleHAiOjE1OTgyNzY4MDMsIm5iZiI6MTU5NzA2NzIwMywianRpIjoiaFhIZk9rNGliOTE3Y2dxaiIsInN1YiI6OTAxNzYsInBydiI6IjIzYmQ1Yzg5NDlmNjAwYWRiMzllNzAxYzQwMDg3MmRiN2E1OTc2Zjcifx.mVhyGxtuHPSqX_TfsF_dJ25yimEZ3pgh24OBALebxMg"
	MY_TOKEN = INIT_TOKEN
	WANT_REFRESH_TOKEN = False
	FREQUENCY_TO_CHECK_CLASS_AVAILABILITY = 1  # 1 second
	FREQUENCY_TO_BOOK = 1  # 1 second

	# Manual config
	USER_NAME = "swsmile1028@gmail.com"
	PASSWORD = "x39wlguv"
	TARGET_CLUB = ClubEnum.Clementi
	CLASS_ID_BLACKLIST = []

	def __init__(self):
		logging.basicConfig(format='%(asctime)s|%(levelname)s|%(filename)s:%(lineno)s [%(funcName)s] |%(message)s',
							level=logging.INFO)

		self.HEADERS = {
			'Host': 'api-mobile.circuithq.com',
			'content-type': 'application/json',
			'accept': '*/*',
			'authorization': 'Bearer ' + self.MY_TOKEN,
			'user-country-code': 'sg',
			'accept-language': 'en-CN;q=1.0, zh-Hans-CN;q=0.9',
			'user-locale': 'cn',
			'user-agent': 'Fitness First Asia/1.10 (com.EvolutionWellness.App.FitnessFirst; build:66; iOS 13.6.0) Alamofire/4.8.2',
			'user-brand-code': 'ff',
		}
	# Disable SSL warnings
	requests.packages.urllib3.disable_warnings()

	def send_http_get(self, url, params):
		response = requests.get(url, headers=self.HEADERS, params=params,
								verify=False)
		return response

	def send_http_post(self, url, cookies=None, data=None):
		response = requests.post(url, headers=self.HEADERS, cookies=cookies, data=data, verify=False)
		return response

	def find_date_list(self):
		date_needed_to_book_list = []
		booked_classes = self.get_booked_classes()
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

	def fail_due_to_invalid_token(self, code):
		fail = code == 401
		if fail:
			logging.error("invali token provided|current token: %s", self.MY_TOKEN)
		return fail

	def refresh_token(self):
		if not self.WANT_REFRESH_TOKEN:
			# TOKEN = INIT_TOKEN
			return True

		response = self.send_http_post('https://api-mobile.circuithq.com/api/v1/auth/token/refresh')
		if self.fail_due_to_invalid_token(response.status_code):
			if self.get_token_by_login():
				return True
			else:
				return False

		# Unknown error
		if not response.ok:
			logging.warning("Unknown error on refresh_token|status_code: %s, response: %s", response.status_code,
							response.text)
			return False

		data = json.loads(response.text)
		token = data["data"]["token"]
		TOKEN = token
		print("We have a new token: " + token)

		return True

	def get_club_id_by_club_enum(self, e):
		if e == ClubEnum.Clementi:
			# 321 Clementi: 19
			return 19
		else:
			return 19

	def get_club_enum_by_club_id(self, club_id):
		club_id = int(club_id)
		if club_id == 19:
			return ClubEnum.Clementi
		else:
			return ClubEnum.Clementi

	def parse_classes(self, classes_dict):
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
			if class_name.find("Personal Training") == -1 and club_id == self.get_club_id_by_club_enum(self.TARGET_CLUB):
				gym_class = GymClass()
				gym_class.class_id = class_id
				gym_class.name = class_name

				gym_class.start_time = datetime.datetime.fromtimestamp(int(timeStart))
				gym_class.end_time = datetime.datetime.fromtimestamp(int(timeEnd))
				gym_class.club = self.get_club_enum_by_club_id(club_id)
				gym_class.capacity = capacity

				class_to_book.append(gym_class)

		return class_to_book

	# Didn't find any available class
	# print("Didn't find any available class")
	def get_token_by_login(self):
		logging.info("try to get a new token...")

		data_dict = {}
		data_dict["captcha_token"] = "batman"
		data_dict["email"] = self.USER_NAME
		data_dict["password"] = self.PASSWORD

		response = self.send_http_post("https://api-mobile.circuithq.com/api/v1/auth/login", data=json.dumps(data_dict))
		response_data = json.loads(response.text)
		if response.status_code == 200:
			if "data" in response_data and "token" in response_data["data"]:
				self.MY_TOKEN = response_data["data"]["token"]
				logging.info("got a new token!!! %s", self.MY_TOKEN)
				return True

		# Cannot continue, because of unknown error
		logging.warning("Unknown error on get_token_by_login|status_code: %s, response: %s", response.status_code,
						response.text)
		return False

	def book_class(self, c):
		# without this Cookie is ok
		# cookies = {
		# 	'ARRAffinity': '94172f5487d231c2d0c7ffe567b886259eb44ddbfd8f88adc109ab9b026ea441',
		# }
		cookies = {}
		data = '{"class_id": ' + str(c.class_id) + '}'

		while True:
			response = self.send_http_post('https://api-mobile.circuithq.com/api/v2/class/book', cookies=cookies,
										   data=data)
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
						time.sleep(self.FREQUENCY_TO_BOOK)
						continue
					elif msg == "booking_errors_too_soon":
						logging.info(
							"[retry] try to book (class_id: %s), but fail due to be too early...|start_time: %s, name: %s",
							c.class_id, c.start_time.strftime("%Y-%m-%d %H:%M:%S"), c.name)

						# TODO
						time.sleep(self.FREQUENCY_TO_BOOK)
						continue
					elif msg == "booking_errors_overlap":
						# logging.info(
						# 	"booked already...|class_id: %s, start_time: %s, name: %s",
						# 	c.class_id, c.start_time.strftime("%Y-%m-%d %H:%M:%S"), c.name)
						return False

			logging.warning("Unknown error on book_class|status_code: %s, response: %s", response.status_code,
							response.text)
			return False

	def get_booked_classes(self):
		booked_classes = []

		while True:
			params = (
				('page', '1'),
				('pageSize', '25'),
			)
			response = self.send_http_get('https://api-mobile.circuithq.com/api/v2/booking/upcoming', params)
			if self.fail_due_to_invalid_token(response.status_code):
				if self.get_token_by_login():
					continue
				else:
					return booked_classes

			# Unknown error
			if not response.ok:
				logging.warning("Unknown error on get_booked_classes|status_code: %s, response: %s",
								response.status_code,
								response.text)
				return booked_classes

			data = json.loads(response.text)
			booked_classes_dict = data["data"]

			for c_dict in booked_classes_dict:
				c = GymClass()
				c.class_id = c_dict["classId"]
				c.name = c_dict["name"]
				c.start_time = datetime.datetime.fromtimestamp(int(c_dict["timeStart"]))
				c.end_time = datetime.datetime.fromtimestamp(int(c_dict["timeStart"]))
				c.club = self.get_club_enum_by_club_id(c_dict["club"]["clubId"])
				booked_classes.append(c)
				logging.info("booked_class: %s", c)

			return booked_classes

	# Return class_ids_to_book
	def query_class_for_a_day(self, date_for_query):
		start_time_for_book_query = date_for_query
		start_time_for_book_query = date_for_query.replace(hour=20)
		start_time_for_book_query = start_time_for_book_query.replace(minute=1)

		end_time_for_book_query = date_for_query
		end_time_for_book_query = date_for_query.replace(hour=22)
		end_time_for_book_query = end_time_for_book_query.replace(minute=30)
		params = (
			('pageSize', '1000'),

			('clubId', str(self.get_club_id_by_club_enum(self.TARGET_CLUB))),
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
					 end_time_for_book_query.strftime('%Y-%m-%d %H:%M:%S'), self.TARGET_CLUB)

		while True:
			response = self.send_http_get('https://api-mobile.circuithq.com/api/v2/class/search/', params)
			data = json.loads(response.text)

			if self.fail_due_to_invalid_token(response.status_code):  # We need to refresh token
				if self.get_token_by_login():
					continue
				else:
					return None
			#  {"error":{"code":10,"messages":[{"message":"errors_token_blacklisted"}]}}
			# if refresh_token():
			# 	continue

			if response.status_code == 200:
				if len(data["data"]) == 1:
					logging.warning("no classed found| check parameters provided|")
					return None

				classes_dict = data["data"]
				return self.parse_classes(classes_dict)
			# time.sleep(FREQUENCY_TO_CHECK_CLASS_AVAILABILITY)

			# Cannot continue, because of unknown error
			logging.warning("Unknown error on query_class|status_code: %s, response: %s", response.status_code,
							response.text)
			return None

	def find_classes_to_book(self, date_needed_to_book_list):
		classes_to_book = []
		for d in date_needed_to_book_list:
			classes_to_book_per_day = self.query_class_for_a_day(d)
			if classes_to_book_per_day:
				classes_to_book.extend(classes_to_book_per_day)
		return classes_to_book

	def book_classes(self, classes_to_book):
		for c in classes_to_book:
			if c.class_id not in self.CLASS_ID_BLACKLIST:
				t = threading.Thread(target=self.book_class, args=(c,))
				t.start()

	def Start(self):
		date_needed_to_book_list = self.find_date_list()
		classes_to_book = self.find_classes_to_book(date_needed_to_book_list)
		self.book_classes(classes_to_book)


b = Mybot()
b.Start()
