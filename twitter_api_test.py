
import tweepy
import pandas as pd

# define API Keys and Access tokens as variables
api_key = "6hLFaYyDGmkPmBwoXKctOoSYi"
api_key_secret = "Fpy9Zz0kH1CTwEdbaDJgdXWTwteePLSfbGwz1WstHZvyzOiplg"
access_token = "2785943655-y2zvUthJViU6mjaWvJ7Ksnk4T4W4dkTkLgQNEdZ"
access_tokent_secret = "6dQYJV3Oz8QFdQZUt9cuEabNs67fs2FE2sw5fkby40oqP"

# authenticate
auth = tweepy.OAuthHandler(api_key, api_key_secret)
auth.set_access_token(access_token, access_tokent_secret)
api = tweepy.API(auth)


# create a list of hashtags of interest
# lst_hashtags = ["#Resolution2020","#VoiceForThePlanet","#EcoFriendly","#ZeroWaste","#ClimateEmergency"]
lst_hashtags = ["#Resolution2020", "#VoiceForThePlanet"]

# search Twitter for relevant tweets based on hashtag
relevant_tweets = api.search(lst_hashtags)

# initiate a list, and store data to it
list = []

for tweet in relevant_tweets:
    twit =[tweet.user.name, tweet.user.location, tweet.text]
    list.append(twit)

# check results
print(list)

# write results to a Pandas df for analysis
tweet_df = pd.DataFrame(list)
tweet_df.head()
