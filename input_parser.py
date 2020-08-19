@staticmethod
def parse_input_time(input_time_to_query):
	try:
		r = datetime.strptime(input_time_to_query, '%H:%M')
		return r
	except Exception as e:
		log.debug("wrong input time format: %s", input_time_to_query)
		return None

@staticmethod
def parse_input_club_name(input_club_name):
	