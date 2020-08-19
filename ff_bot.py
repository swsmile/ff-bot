#!/usr/bin/python3
import time
import logging
import requests
import json
import datetime

import threading
from enum import Enum, unique
import argparse
import my_until


@unique
class ClubEnum(Enum):
	Clementi = 0  # Sun的value被设定为0


class GymClass:
	class_id = 0
	name = ""
	start_time = my_until.get_current_time()
	end_time = my_until.get_current_time()
	club = ClubEnum.Clementi
	capacity = 0

	def __str__(self):
		return "GymClass - name: {}, class_id: {}, start_time: {}, end_time: {}, club: {}".format(self.name,
																								  self.class_id,
																								  self.start_time,
																								  self.end_time,
																								  self.club)


class Mybot:
	TOKEN = ""
	WANT_REFRESH_TOKEN = False
	# FREQUENCY_TO_CHECK_CLASS_AVAILABILITY = 1  # 1 second
	FREQUENCY_TO_BOOK_DURING_ALMOST_BOOKABLE_PERIOD = 0.3  # 0.3s
	FREQUENCY_TO_BOOK_BEFORE_ALMOST_BOOKABLE_PERIOD = 5  # 5s
	# FREQUENCY_TO_BOOK_DURING_WARMUP_PERIOD = 2  # 2s
	EARLIEST_BOOKABLE_HOUR = 46  # 2020-8-13 the earliest bookable time is 46 hours

	USER_NAME = ""
	PASSWORD = ""
	TARGET_CLUB = ClubEnum.Clementi
	CLASS_ID_BLACKLIST = []

	def get_headers(self):
		headers = {
			'Host': 'api-mobile.circuithq.com',
			'content-type': 'application/json',
			'accept': '*/*',
			'authorization': 'Bearer ' + self.TOKEN,
			'user-country-code': 'sg',
			'accept-language': 'en-CN;q=1.0, zh-Hans-CN;q=0.9',
			'user-locale': 'cn',
			'user-agent': 'Fitness First Asia/1.10 (com.EvolutionWellness.App.FitnessFirst; build:66; iOS 13.6.0) Alamofire/4.8.2',
			'user-brand-code': 'ff',
		}
		return headers

	def parse_account_passward(self):
		self.PASSWORD = self.args.password
		self.USER_NAME = self.args.account

	def __init__(self):
		logging.basicConfig(format='%(asctime)s|%(levelname)s|%(filename)s:%(lineno)s [%(funcName)s] |%(message)s',
							level=logging.INFO)
		# Disable SSL warnings
		requests.packages.urllib3.disable_warnings()

		# Parse parameters
		parser = argparse.ArgumentParser(description='Get FF slot for u automatically.')
		parser.add_argument('--account', "-u", action='store', dest='account', type=str, default="",
							help="your account for FF App")
		parser.add_argument('--password', '-p', action='store', dest='password', type=str, default="",
							help="your password for FF App")
		# TODO booking filters


		self.args = parser.parse_args()

	def send_http_get(self, url, params):
		response = requests.get(url, headers=self.get_headers(), params=params,
								verify=False)
		return response

	def send_http_post(self, url, cookies=None, data=None):
		response = requests.post(url, headers=self.get_headers(), cookies=cookies, data=data, verify=False)
		return response

	def find_date_list(self):
		date_needed_to_book_list = []
		booked_classes = self.get_booked_classes()
		now = my_until.get_current_time()

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
			logging.warning("invali token provided|current token: %s", self.TOKEN)
		return fail

	def refresh_token(self):
		if not self.WANT_REFRESH_TOKEN:
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
		self.TOKEN = token
		logging.info("We have a new token: %s", token)

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
			if class_name.find("Personal Training") == -1 and club_id == self.get_club_id_by_club_enum(
					self.TARGET_CLUB):
				gym_class = GymClass()
				gym_class.class_id = class_id
				gym_class.name = class_name

				gym_class.start_time = datetime.datetime.fromtimestamp(int(timeStart))
				gym_class.end_time = datetime.datetime.fromtimestamp(int(timeEnd))
				gym_class.club = self.get_club_enum_by_club_id(club_id)
				gym_class.capacity = capacity

				class_to_book.append(gym_class)

		return class_to_book

	"""
	"""

	def get_token_by_login(self):
		logging.info("try to get a new token...")

		data_dict = {}
		data_dict["captcha_token"] = "batman"
		data_dict["email"] = self.USER_NAME
		data_dict["password"] = self.PASSWORD

		response = self.send_http_post("https://api-mobile.circuithq.com/api/v1/auth/login", data=json.dumps(data_dict))
		response_dict = json.loads(response.text)
		if response.status_code == 200:
			if "data" in response_dict and "token" in response_dict["data"]:
				self.TOKEN = response_dict["data"]["token"]
				logging.info("got a new token!!! %s", self.TOKEN)
				return True
		elif response.status_code == 404:
			if "error" in response_dict:
				if "messages" in response_dict["error"]:
					if len(response_dict["error"]["messages"]) > 0:
						if response_dict["error"]["messages"][0]:
							if response_dict["error"]["messages"][0].get("message",
																		 "") == "auth_errors_invalid_credentials":
								logging.warning("wrong account or password")
								return False

		# Cannot continue, because of unknown error
		logging.warning("Unknown error on get_token_by_login|status_code: %s, response: %s", response.status_code,
						response.text)
		return False

	def book_class(self, c):
		# Without this Cookie is ok
		# cookies = {
		# 	'ARRAffinity': '94172f5487d231c2d0c7ffe567b886259eb44ddbfd8f88adc109ab9b026ea441',
		# }
		cookies = {}
		data = '{"class_id": ' + str(c.class_id) + '}'

		while True:
			# TODO check success set before booking

			response = self.send_http_post('https://api-mobile.circuithq.com/api/v2/class/book', cookies=cookies,
										   data=data)
			response_data = json.loads(response.text)
			if response.status_code == 200:
				logging.info("we make it")
				# TODO send to MM
				booked_class = data["data"]

				# TODO once done, put it into success set
				return True

			if response.status_code == 400:
				if "error" in response_data and response_data["error"] and "code" in response_data["error"] and \
						response_data["error"]["code"] == 10 and "messages" in response_data["error"] and len(
					response_data["error"]["messages"]) > 0:
					msg = response_data["error"]["messages"][0]["message"]

					# 2020-08-12 found error msg is changed
					if msg == "booking_errors_too_late_sg":
						# logging.info(
						# 	"we are too late to book or we have booked it, so give up, class_id: %s, start_time: %s, name: %s",
						# 	c.class_id, c.start_time.strftime("%Y-%m-%d %H:%M:%S"), c.name)
						return False
					elif msg == "booking_errors_fully_booked":
						logging.info(
							"[retry] try to book (class_id: %s), but fail due to full capacity...|start_time: %s, name: %s",
							c.class_id, c.start_time.strftime("%Y-%m-%d %H:%M:%S"), c.name)

						time.sleep(Mybot.FREQUENCY_TO_BOOK_DURING_ALMOST_BOOKABLE_PERIOD)
						continue
					elif msg == "booking_errors_too_soon":
						logging.info(
							"[retry] try to book (class_id: %s), but fail due to be too early...|start_time: %s, name: %s",
							c.class_id, c.start_time.strftime("%Y-%m-%d %H:%M:%S"), c.name)

						now = my_until.get_current_time()
						diff = c.start_time - now
						if diff.hour == Mybot.EARLIEST_BOOKABLE_HOUR and diff.minute <= 5:
							time.sleep(Mybot.FREQUENCY_TO_BOOK)
						elif (diff.hour == Mybot.EARLIEST_BOOKABLE_HOUR and diff.minute > 5) or (
								diff.hour > Mybot.EARLIEST_BOOKABLE_HOUR):
							time.sleep(Mybot.FREQUENCY_TO_BOOK_BEFORE_ALMOST_BOOKABLE_PERIOD)
						else:
							logging.warning(
								"Unknown error on book_class|status_code: %s, response: %s, c.start_time: %s, now: %s",
								response.status_code,
								response.text, c.start_time, now)
							return False

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

		logging.info("query class info..., start_time_for_book_query: %s, end_time_for_book_query: %s, club: %s",
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

				logging.info("got class info already:")
				classes = self.parse_classes(classes_dict)
				(logging.info("%s", c) for c in classes)
				return classes
			# time.sleep(FREQUENCY_TO_CHECK_CLASS_AVAILABILITY)

			# Cannot continue, because of unknown error
			logging.warning("Unknown error on query_class|status_code: %s, response: %s", response.status_code,
							response.text)
			return None

	def find_classes_to_book_by_filter(self, start_time_to_book, end_time_to_book, club_id):
		# TODO
		pass

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

	def parse_booking_filters(self):
		# TODO
		pass

	def Start(self):
		self.parse_account_passward()

		# Verify account and password
		if not self.get_token_by_login():
			return

		self.parse_booking_filters()

		# date_needed_to_book_list = self.find_date_list()
		# classes_to_book = self.find_classes_to_book(date_needed_to_book_list)

		classes_to_book = self.find_classes_to_book_by_filter()
		self.book_classes(classes_to_book)


if __name__ == "__main__":
	b = Mybot()
	b.Start()
