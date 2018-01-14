import paws as config
import sqlite3
import praw
import re
import datetime as dt
import time
import sys

sub_name 		= "dogemarket"
sub_name_scam	= "dogecoinscamwatch"

sub_name		= "fricktest"
sub_name_scam	= "fricktest2"

post_id			= "7kfn74"
comment_limit 	= 50
post_limit		= 50
sleep_seconds	= 60

test_mode 		= True
debug_mode 		= False
show_sql 		= False

version 		= "0.9b" 	
user_agent 		= "/r/{0} bot - v{1}".format(sub_name, version)

#KEYWORDS
kw_trade		= "!CONFIRMED"	#UPPER CASE
kw_userstatus	= "!USERSTATUS"
kw_status_list	= ["SCAMMER","CONVICTED","CLEAN"]

db_name			= "dogemarket.db"
tbl_trades 		= "doge_trades"
tbl_first_trade = "doge_first_trade"
tbl_flairs		= "doge_flairs"
tbl_scam_posts  = "doge_scam_posts"
tbl_user_status	= "doge_user_status"
tbl_ignore		= "doge_ignore"

def BotLogin():

	print("Logging in as %s..." %config.username) 	#LOGIN USING CREDENTIALS FROM CONFIG FILE (SEPERATE FILE)
	r = praw.Reddit(username = config.username,
					password = config.password,
					client_id = config.client_id,
					client_secret = config.client_secret,
					user_agent = user_agent)
					
	#SEND THE LOGGED IN VARIABLE BACK
	print("Logged in at %s" % CurrentTime())
	print("Subreddits: %s"%sub_name+ "\n"*3 )

	#SEND THE LOGGED IN OBJECT BACK
	return r
	
def ProcessComments(r):

	print("*"*50)
	print("Starting ProcessComments...")
	
	try:
		comments = list(r.subreddit(sub_name).comments(limit=comment_limit))
	except:
		print("#"*25)
		print("ERROR GETTING COMMENTS FROM REDDIT")
		print("#"*25)
		
	for comment in comments:
	
		#ONLY PROCESS FROM SPECIFIC POST
		if not comment.submission.id == post_id:
			continue

		#IF THE COMMENT BEGGINS WITH THE TRADE TRIGGER
		if str(comment.body[0:10]).upper() == kw_trade:
			print(comment.id)

			if comment.is_root:
				print("\tIGNORING - Top Level Comment\n")
				continue							

			#CHECK IF ITS IN THE IGNORE LIST USING SUBMISSION ID
			strSQL = "SELECT Reason FROM {0} WHERE CommentID = ?".format(tbl_ignore)
			
			if show_sql:
				print("\t\t{0}".format(strSQL))
			
			cur.execute(strSQL, (comment.id,))
			
			#GET THE REASON
			ignore_reason = None			
			ignore_reason = cur.fetchone()
			
			#IF THERE IS A REASON, MOVE ON
			if not ignore_reason is None:
				print("\tIGNORING - post in ignore list ({0})\n".format(ignore_reason[0]))
				continue
			
			if debug_mode:
				print("\t\tParent Comment: %s" %comment.parent().id)
			
			#CHECK IF THE TRADE HAS BEEN PROCESSED ALREADY
			strSQL = "SELECT ParentCommentID FROM %s WHERE ParentCommentID = ?" %tbl_trades

			if show_sql:
				print("\t\t%s" %strSQL)
			
			cur.execute(strSQL,(comment.parent().id,))
			
			if cur.fetchone():
				print("\tTrade already processed!\n")
				continue
			else:
				if debug_mode:
					print("\t\tNothing returned - new trade!\n")
				
			#IF NOT PROCESSED, GET THE USERNAMES
			comm_parent = comment.parent()
			comm_parent_body = comm_parent.body
			comm_parent_author = str(comm_parent.author)
			
			#TAKE THIS COMMENTS DETAILS
			comm_body = comment.body
			comm_author = str(comment.author)
						
			#FIND ALL USERNAMES IN THE PARENT COMMENT
			all_matches = re.findall(r'\/u\/([^\s]+)', comm_parent_body, re.I | re.U)
			
			#LIST ALL MATCHES
			if debug_mode:
			
				print("\t\tFound %s username matches in comment: %s\n" %(len(all_matches),all_matches))
				
			#SECOND USERNAME
			if len(all_matches) == 0:
				print("\tNo usernames found in comment!")
				continue
			
			#CONTINUE WITH USERNAME
			second_user = all_matches[0]
			if debug_mode:
				print("\t\tUser in comment: %s\n" %second_user)
				print("\t\tChild Author: %s" %comm_author)
				print("\t\tParent Author: %s" %comm_parent_author)
				
			#CONFIRM THAT THE PERSON COMMENTING IS THE USER MENTIONED
			if not second_user.upper() == comm_author.upper():
				print("\tUser ({0}) is not in parent comment - ignoring...!\n".format(second_user))
				
				#ADD TO IGNORE LIST
				strSQL = "INSERT INTO {0} (ProcessedTime, CommentID, Reason) VALUES ('{1}',?, '{2}')".format(tbl_ignore,CurrentTime(),"User not mentioned")
				
				if show_sql:
					print("\t\t{0}".format(strSQL))
				
				cur.execute(strSQL,(comment.id,))
				sql.commit()
				
				continue

			#CONFIRM THAT THE USER IS NOT AWARDING A POINT TO THEM SELVES
			if comm_parent_author == comm_author:
				print("\tUser ({0}) awarding point to self!".format(comm_author))
				continue
			else:
				print("\tConfirmed - Trade between: %s and %s...\n" %(comm_parent_author,comm_author))
				
			#GET BOTH USERS FLAIRS
			parent_flair = str(comm_parent.author_flair_text)
			child_flair = str(comment.author_flair_text)
			
			##############################
			#    PARENT COMMENT TRADER
			##############################
			
			#EMPTY THE VARIABLE
			parent_trade = ""

			#USE REGEX TO MATCH THE BEGINNING OF THE FLAIR TO FIND A 4 DIGIT NUMBER UP TO /
			all_matches = re.findall(r'^[0-9]{1,4}\/', parent_flair, re.I | re.U)
						
			#IF MATCH FOUND
			if len(all_matches) > 0:

				#TAKE THE FIRST MATCH
				parent_trade = str(all_matches[0])
				
				#REMOVE THE / IF NECESSARY
				if parent_trade[-1] == "/":
					parent_trade = parent_trade[0:-1]
				
				if debug_mode:
					print("\t\tParent Flair: %s" %parent_trade)
			
			#IF NOT NUMERIC, THEN RESET IT TO 0
			if not parent_trade.isnumeric():
				if debug_mode:
					print("\t\tNON-NUMERIC FLAIR - Setting flair to 0")
				parent_trade = 0
			else:
				parent_trade = int(parent_trade)
				
			#ONCE FLAIRS HAVE BEEN SET, INCREMEENT
			parent_trade += 1

			if debug_mode:
				print("\t\tNew Parent Flair: %s\n" %parent_trade)
			
			#GET THE EARLIEST TRADE			
			strSQL = "SELECT FirstTradeDate FROM %s WHERE Redditor = ? ORDER BY FirstTradeDate ASC" %tbl_first_trade

			if show_sql:
				print("\t\t%s" %strSQL)

			cur.execute(strSQL, (comm_parent_author,))

			#EMPTY THE VARIABLE
			parent_first_trade = None
			
			#GET THE RESULT
			try:
				parent_first_trade = cur.fetchone()[0]
			except:
				print("\t\tNo first trade data returned!")
				
			#IF STILL EMPTY, THEN 
			if parent_first_trade is None:
			
				#FIRST TRADE IS IN 0 DAYS
				print("\tParent First Trade - Setting years to 0...")
				parent_first_trade = 0
				
				#ADD TO DATABASE
				strSQL = "INSERT INTO %s Values('%s',?,?)" %(tbl_first_trade,CurrentTime())
				
				if show_sql:
					print("\t\t%s" %strSQL)
				
				cur.execute(strSQL,(comm_parent_author,ConvertUTC(comm_parent.created_utc),))
				sql.commit()
				
			else:
			
				#FORMAT THE TRADE DATE
				d1 = dt.datetime.strptime(parent_first_trade, "%Y-%m-%d %H:%M:%S")
				if debug_mode:
					print("\t\t\tFirst Trade: {0}".format(d1))
				
				#FORMAT THE CURRENT DATE
				d2 = dt.datetime.strptime(str(CurrentTime()), "%Y-%m-%d %H:%M:%S")
				if debug_mode:
					print("\t\t\tNow: {0}".format(d2))
				
				#DIFFERENCE BETWEEN DATES
				parent_first_trade = abs(d2.year - d1.year)
				if debug_mode:
					print("\t\tYears since trade: %s\n" %parent_first_trade)
			
			parent_new_flair = "%s/%s" %(parent_trade,parent_first_trade)
			print("\tParent New flair: %s" %parent_new_flair)
			
			#############################
			#    CHILD COMMENT TRADER
			#############################

			#EMPTY THE VARIABLE
			child_trade = ""

			#USE REGEX TO MATCH THE BEGINNING PART
			all_matches = re.findall(r'^[0-9]{1,4}\/', child_flair, re.I | re.U)
			
			#IF MATCH FOUND
			if len(all_matches) > 0:

				#TAKE THE FIRST MATCH
				child_trade = str(all_matches[0])
				
				#REMOVE THE / IF NECESSARY
				if child_trade[-1] == "/":
					child_trade = child_trade[0:-1]
				
				if debug_mode:
					print("\n\t\tChild Flair: %s" %child_trade)
			
			#IF NOT NUMERIC, THEN RESET IT TO 0
			if not child_trade.isnumeric():
				if debug_mode:
					print("\t\tNON-NUMERIC FLAIR - Setting flair to 0")
				child_trade = 0
			else:
				child_trade = int(child_trade)
				
			#ONCE FLAIRS HAVE BEEN SET, INCREMEENT
			child_trade += 1

			if debug_mode:
				print("\t\tNew Child Flair: %s\n" %child_trade)
			
			#GET THE EARLIEST TRADE	FOR THE CHILD TRADE
			strSQL = "SELECT FirstTradeDate FROM %s WHERE Redditor = ?" %tbl_first_trade

			if show_sql:
				print("\t\t%s" %strSQL)

			cur.execute(strSQL, (comm_author,))

			#EMPTY THE VARIABLE
			child_first_trade = None
			
			#GET THE RESULT
			try:
				child_first_trade = str(cur.fetchone()[0])
			except:
				pass
				
			#IF STILL EMPTY, THEN 
			if child_first_trade is None:
			
				#FIRST TRADE IS IN 0 DAYS
				print("\tChild First Trade - Setting years to 0...")
				child_first_trade = 0
				
				#ADD TO DATABASE
				strSQL = "INSERT INTO %s Values('%s',?,?)" %(tbl_first_trade,CurrentTime())
				
				if show_sql:
					print("\t\t%s" %strSQL)
				
				cur.execute(strSQL,(comm_author,ConvertUTC(comm_parent.created_utc),))
				sql.commit()
				
			else:
				
				#FORMAT THE FIRST TRADE DATE
				d1 = dt.datetime.strptime(child_first_trade, "%Y-%m-%d %H:%M:%S")
				if debug_mode:
					print("\t\t\tFirst Trade: {0}".format(d1))
				
				#FORMAT THE CURRENT DATE TIME
				d2 = dt.datetime.strptime(str(CurrentTime()), "%Y-%m-%d %H:%M:%S")
				if debug_mode:
					print("\t\t\tNow: {0}".format(d2))

				#DIFFERENCE BETWEEN DATES					
				child_first_trade = abs(d2.year - d1.year)
				if debug_mode:
					print("\t\tYears since trade: %s\n" %child_first_trade)
			
			child_new_flair = "%s/%s" %(child_trade,child_first_trade)
			print("\tChild New flair: %s" %child_new_flair)
			
			########################
			#    SET USER STATUS
			########################
			
			#GET THE USER STATUS FROM ANOTHER MODULE
			child_user_status = GetUserStatus(r, comm_author)
			parent_user_status = GetUserStatus(r, comm_parent_author)
			
			########################
			#    FINALISE FLAIRS
			########################

			child_new_flair = "{0}/{1}".format(child_new_flair, child_user_status)
			parent_new_flair = "{0}/{1}".format(parent_new_flair, parent_user_status)
			
			########################
			#    INSERT IN TABLE
			########################

			strSQL = "INSERT INTO %s VALUES('%s', ?, ?, ?, ?, ?)" %(tbl_trades, CurrentTime())
			
			if show_sql:
				print("\t\t%s" %strSQL)
				
			cur.execute(strSQL, (comment.id, comment.parent().id, comm_parent_author, comm_author, comm_body,))
			sql.commit()

			####################
			#    SET FLAIRS
			####################			
			
			#DETERMINE CSS CLASS
			print("\n\tSetting child flair to {0} - {1}...\n".format(comm_author, child_new_flair))
			if comm_author in moderators:
				flair_class = "moderator"
			else:
				flair_class = "number"

			#SET THE FLAIRS				
			try:
				comment.subreddit.flair.set(comm_author, child_new_flair, flair_class)
				r.subreddit(sub_name_scam).flair.set(comm_author, child_new_flair, flair_class)
			except:
				print("\tERROR SETTING CHILD FLAIR!")

			strSQL = "INSERT INTO %s VALUES('%s', ?, ?, ?)" %(tbl_flairs, CurrentTime())
						
			if show_sql:
				print("\t\t%s" %strSQL)
			
			#UPDATE TABLE WITH RECORD
			cur.execute(strSQL, (comm_author, child_trade, child_new_flair,))
			sql.commit()
			
			#SET PARENT COMMENT FLAIR
			print("\tSetting parent flair to {0} - {1}...\n".format(comm_parent_author, parent_new_flair))

			if comm_parent_author in moderators:
				flair_class = "moderator"
			else:
				flair_class = "number"
			
			#SET THE FLAIR IN BOTH SUBREDDITS
			try:
				comment.subreddit.flair.set(comm_parent_author, parent_new_flair, flair_class)
				r.subreddit(sub_name_scam).flair.set(comm_parent_author, parent_new_flair, flair_class)
			except:
				print("\tERROR SETTING PARENT FLAIR!")
			
			#UPDATE DATABASE
			strSQL = "INSERT INTO %s VALUES('%s', '%s', '%s', '%s')" %(tbl_flairs, CurrentTime(), comm_parent_author, parent_trade, parent_new_flair)
			if show_sql:
				print("\t\t%s" %strSQL)
			
			cur.execute(strSQL)
			sql.commit()
				
			#REPLY WITH CONFIRMATION OF TRADE
			if debug_mode:
				print("\t\tSending reply...")
			
			try:
				comm = comment.reply(config.trade_complete_reply.format(comm_author,comm_parent_author))
				comm.mod.distinguish()
			except:
				print("\tERROR SENDING END OF PROCESS REPLY!")

			print("-"*25)

	print("Finishing ProcessComments...")
	print("*"*50)

def GetModerators(r):

	print("Starting - GetModerators...")
			
	#GET MODERATORS FOR EVERY SUB
	all_mods = list(r.subreddit(sub_name).moderator())

	#CREATE A LIST				
	for moderator in all_mods:
		moderators.append(moderator.name)

	#CONFIRMATION
	#if debug_mode:
	#	print(mod_list)

	if debug_mode:
		print(moderators)
	
	if debug_mode:
		print("Retreived %s moderators..." %len(moderators))			
	
	#LINE BREAK
	print("\n")
			
def GetScamPosts(r):

	print("*"*50)
	print("Starting GetScamPosts...")
	
	all_posts = list(r.subreddit(sub_name_scam).new(limit=post_limit))
	
	for post in all_posts:
		
		#IF POST TITLE STARTS WITH SCAMMER
		if post.title[0:9].upper() == "[SCAMMER]":
		
			print(post.id)
		
			post_title = post.title
			#CHECK IF IT'S ALREADY BEEN PROCESSED
			strSQL = "SELECT * FROM %s WHERE PostID = ?" %tbl_scam_posts
			
			if show_sql:
				print("\t\t%s" %strSQL)
				
			cur.execute(strSQL, (post.id,))
			
			#IF ANYTHING RETURNED, THEN IGNORE
			if cur.fetchone():
				print("\tPost already processed.\n")
				continue
			
			#PRINT POST
			print("\t%s - %s" %(post.author, post.title))
				
			#FIND THE USERNAME IN THE TITLE
			all_matches = re.findall(r'\/u\/([^\s]+)', post_title, re.I | re.U)
			
			#LIST ALL MATCHES
			if debug_mode:
				print("\t\tFound %s matches : %s\n" %(len(all_matches),all_matches))
				
			#IF NOTHING FOUND, THEN CONTINUE
			if len(all_matches) == 0:
				print("\tNo usernames found in post title!")
				continue
			
			#EXTRACT USERNAME
			scammer = all_matches[0]
			
			#ADD TO DATABASE
			strSQL = "INSERT INTO %s VALUES('%s', ? , ?, ?, ?)" %(tbl_scam_posts,CurrentTime())
			
			cur.execute(strSQL,(str(post.id),scammer,str(post.author),str(post.title),))
			sql.commit()
			
			mm_subject = "New Scammer Post - %s" %scammer
			mm_message = """
			
Scammer: /u/{0}    
Accuser: /u/{1}


[View Post]({2})

____


[Confirm SCAMMER](https://www.reddit.com/message/compose/?to={3}&subject={4} Scammer&message=/u/{0})

[Leave as CONVICTED](https://www.reddit.com/message/compose/?to={3}&subject={4} Convicted&message=/u/{0})

[Mark CLEAN](https://www.reddit.com/message/compose/?to={3}&subject={4} Clean&message=/u/{0})

""".format(scammer, post.author, post.permalink, config.username, kw_userstatus)

			print("\tSending modmail notification...")
			#SEND MODMAIL AFTER GETTING A NEW POST
			try:
				pass
				r.subreddit(sub_name).message(mm_subject,mm_message)
			except:
				print("\tERROR SENDING MODMAIL!")
			
			#REPLY WITH DEFAULT MESSAGE
			try:
				print("\tReplying with comment...")
				comm = post.reply(config.new_scam_post_reply)			
				#CANNOT DISTINGUISH - NOT A MODERATOR
				#comm.mod.distinguish()
			#except RATELIMIT:
			#	print("\tERROR: Posting too much error!")
			except:
				print("\tERROR SENDING NEW SCAM POST REPLY!")
			
	print("\nFinishing GetScamPosts...")
	print("*"*50)
			
def GetInbox(r):

	print("*"*50)
	print("Starting GetInbox...")

	print("\tGetting all unread messages from Inbox...\n")
	msgs = r.inbox.unread(limit=None)
		
	for msg in msgs:

		#LENGTH OF THE FIRST KEYWORD
		len_kw1 = int(len(kw_userstatus))

		#IF SCAMCHECK MESSAGES		
		if str(msg.subject)[0:len_kw1].upper() == kw_userstatus:
		
			#CHECK THE USER IS A MODERATORS
			if msg.author not in moderators:
				print("\tMessage author ({0}) is not a moderator!".format(msg.author))
				continue
			
			#IF THERE IS MORE INFO BEYOND JUST THE KEYWORD
			if len(msg.subject) <= len_kw1:
				print("\tNo content in message...")
				continue
		
			#MARK THE MESSAGE AS UNREAD STRAIGHTAWAY
			msg.mark_read()
	
			print("\tNew {0} message from Mod: {1}".format(kw_userstatus, msg.author))

			#EMPTY THE VARIABLE
			new_status = None
			
			new_status = str(msg.subject).replace("{0} ".format(kw_userstatus), "")
							
			all_matches = None
			
			#GET THE USERNAME FROM THE START OF THE BODY
			all_matches = re.findall(r'^\/u\/([^\s]+)', msg.body, re.I | re.U)			

			if all_matches is None:
				print("\tNo username found in beginning of body!")
			else:
				if debug_mode:
					print("\t\tUser in body: {0}".format(all_matches[0]))
				
			#TAKE THE NAME OF THE USER - REMOVE THE /U/
			user_to_update = all_matches[0]
						
			#UPDATE THE SCAMMER TABLE WITH THE DETAILS
			strSQL = "INSERT INTO {0} VALUES('{1}', ?, ?, ?)".format(tbl_user_status, CurrentTime())
			
			if show_sql:
				print("\t\t{0}".format(strSQL))
			
			cur.execute(strSQL, (user_to_update, new_status, str(msg.author),))
			sql.commit()
			
			#CONFIRMATION
			print("\tAdded {0} as {1} to database.\n".format(user_to_update,new_status))
			
			#############################
			#    UPDATE USERS'S FLAIR
			#############################
			
			#GET THE CURRENT CSS - otherwise a dictionary containing the keys flair_css_class, flair_text, and user.
			user_css = list(r.subreddit(sub_name).flair(redditor=user_to_update))[0]
			
			#TAKE WHAT YOU NEED
			cur_flair_class = user_css["flair_css_class"]
			cur_flair_text = user_css["flair_text"]
			
			if debug_mode:
				print("\n\t\tCurrent Flair Class: {0}".format(cur_flair_class))
				print("\t\tCurrent Flair Text: {0}\n".format(cur_flair_text))
			
			#TAKE THE CURRENT TEXT, SPLIT BY / AND THEN PUT TOGETHER
			split_flair_text = cur_flair_text.split("/")
			
			#EMPTY VARIABLE
			new_flair_text = None
			
			#LOOP THROUGH AND GET FIRST TWO
			for x in range(0,2):
			
				if new_flair_text is None:
					new_flair_text = split_flair_text[x]
				else:
					new_flair_text = new_flair_text + "/" + split_flair_text[x]

				if debug_mode:
					print("\tLoop {0}: {1}".format(x, new_flair_text))					
			
			#THEN ADD THE NEW PART
			new_flair_text = new_flair_text + "/" + new_status
			
			print("\tNew Flair: {0}".format(new_flair_text))
			
			#UPDATE THE CSS TO THE NEW CSS, USE SAME CLASS]
			try:
				r.subreddit(sub_name).flair.set(user_to_update, new_flair_text, cur_flair_class)
			except:
				print("\tERROR SETTING NEW FLAIR!")
				
			#IF THE USER IS A SCAMMER, THEN 
			if "SCAMMER" in new_status.upper():
				if not test_mode:
					print("\tBanning user ({0}) from sub...".format(user_to_update))
					r.subreddit(sub_name).banned.add(user_to_update, ban_reason="SCAMMER")
				else:
					print("\tTEST MODE - User should be banned now.")
			
		else:
			if debug_mode:
				print("\t{0} - not processed.\n".format(msg.subject))

	print("Finishing GetInbox...")
	print("*"*50)
				
def GetUserStatus(r, uName):

	#GET THE DATA, SORTED BY DATA, DESCENDING	
	print("\n\tGetting user status for {0}".format(uName))

	#IF THE USER IS A MODERATOR, THEN RETURN MODERATOR
	if uName in moderators:
		print("\tStatus: Mod\n")
		return "Mod"
	
	strSQL = "SELECT Status FROM {0} WHERE Redditor = ? ORDER BY ProcessedTime DESC".format(tbl_user_status)
	
	if show_sql:
		print("\t\t{0}".format(strSQL))
	
	cur.execute(strSQL, (uName,))
	
	scam_data 	= None
	user_status = None
	
	#IF NO DATA RETURNED, THEN USER IS CLEAN
	try:
		#GET THE DATA BACK BUT ONLY THE FIRST RESULT
		scam_data = cur.fetchone()[0]
		if debug_mode:
			print("\t\tReturned: {0}".format(scam_data))
	except:
		pass
	
	#IF SOMETHING WAS RETURNED, THEN CHECK IT
	if scam_data is None:
		print("\tNo user data - CLEAN")
		user_status = "CLEAN"		
	else:
		user_status = scam_data	
		print("\tUser is: {0}\n".format(user_status))
		
	return user_status
		
	
def db_check():

	print("Checking database...")
	#CONNECTION TO DATABASE GLOBALLY
	
	#RUN ONLY ONCE EVERYTIME YOU RUN IT
	cur.execute("CREATE TABLE IF NOT EXISTS %s (ProcessedTime TEXT, CommentID TEXT, ParentCommentID TEXT, Parent TEXT, Child TEXT, Comment TEXT)" %tbl_trades)
	cur.execute("CREATE TABLE IF NOT EXISTS %s (ProcessedTime TEXT, Redditor TEXT, FirstTradeDate TEXT)" %tbl_first_trade)
	cur.execute("CREATE TABLE IF NOT EXISTS %s (ProcessedTime TEXT, Redditor TEXT, TradeCount INTEGER, NewFlair TEXT)" %tbl_flairs)
	cur.execute("CREATE TABLE IF NOT EXISTS %s (ProcessedTime TEXT, PostID TEXT, Scammer TEXT, Accuser TEXT, Title TEXT)" %tbl_scam_posts)
	cur.execute("CREATE TABLE IF NOT EXISTS %s (ProcessedTime TEXT, Redditor TEXT, Status TEXT, ModName TEXT)" %tbl_user_status)
	cur.execute("CREATE TABLE IF NOT EXISTS %s (ProcessedTime TEXT, PostID TEXT, CommentID TEXT, Reason TEXT)" %tbl_ignore)
	
def CurrentTime():
	return dt.datetime.today().replace(microsecond=0)

def ConvertUTC(utcTime):
	result =  dt.datetime.fromtimestamp(int(utcTime)).strftime('%Y-%m-%d %H:%M:%S')
	return result

try:
	print("Connecting to %s..." %db_name)
	sql = sqlite3.connect(db_name)
	cur = sql.cursor()
except:
	print("ERROR - QUITTING - %s database not found!" %db_name)
	sys.exit()

#ONLY LOG IN ON NON-TEST MODE
r = BotLogin()

moderators = []
GetModerators(r)

while True:
	db_check()	
	GetScamPosts(r)
	ProcessComments(r)
	GetInbox(r)
	
	print("Sleeping for %s seconds...\n\n" %sleep_seconds)
	time.sleep(sleep_seconds)