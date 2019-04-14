from ground_truths import ground_truths_politicians, ground_truths_pundits
from re import sub
import sqlite3
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn import linear_model
from nonsense_tester import returnNonsense

def getAllTweetsOneString(handle, RTs=True, sentiment=None, limit=0, exclude=None):
    connection = sqlite3.connect('tweet_data.db')

    sql = "select cleaned from tweet_text where author_handle = '{}'".format(handle)
    if RTs == False:
        sql += " and tweet not like '%RT%'"
    if sentiment != None:
        sql += " and sentiment = '{}'".format(sentiment)
    if exclude != None:
        sql += "and author_handle not in {}".format(str(exclude))
    if limit != 0:
        sql += " limit {}".format(limit)

    all_tweets = pd.read_sql_query(sql, connection)

    connection.close()
    return sub('\n', '', ' '.join(all_tweets['cleaned'].tolist()))

class VectorComparisonModel:
    def __init__(self, testuser=None, TFIDF=True, ignore=tuple(), limit=0, sentiment=None, RTs=True):
        self.rts = RTs
        self.sentiment = sentiment
        self.limit = limit
        self.ignore = ignore

        if testuser == None:
            self.training_users = [x for x in ground_truths_politicians.keys() if x not in ignore]
            self.test_users = [y for y in ground_truths_pundits.keys() if y not in ignore]
            self.ytrain = np.array([list(ground_truths_politicians[x]) for x in self.training_users])
            self.ytest = np.array([list(ground_truths_pundits[x]) for x in self.test_users])
        else:
            self.test_users = [testuser]
            self.training_users = [x for x in ground_truths_politicians.keys() if x not in ignore and x != testuser]
            self.ytrain = np.array([list(ground_truths_politicians[x]) for x in self.training_users])
            self.ytest = np.array([list(ground_truths_politicians[x]) for x in self.test_users])

        if TFIDF == True:
            self.vectorizer = TfidfVectorizer()
        else:
            self.vectorizer = CountVectorizer()

    def makeDataFrames(self):
        # training df
        training_users_tweets_dict = {x: getAllTweetsOneString(x, self.rts, self.sentiment, self.limit, self.ignore)
                                      for x in self.training_users if x not in self.ignore}
        training_users_tweets_df = pd.DataFrame.from_dict(training_users_tweets_dict, orient='index',
                                                          columns=['cleaned'])

        # testing df
        test_users_tweets_dict = {x: getAllTweetsOneString(x, self.rts, self.sentiment, self.limit, self.ignore)
                                  for x in self.test_users if x not in self.ignore}
        test_users_tweets_df = pd.DataFrame.from_dict(test_users_tweets_dict, orient='index', columns=['cleaned'])

        return training_users_tweets_df, test_users_tweets_df

    def createVectors(self, training, testing):
        training['tweets'] = training['cleaned']
        testing['tweets'] = testing['cleaned']

        # fit vectorizer
        # self.vectorizer.fit(training['tweets'].append(testing['tweets']))
        self.vectorizer.fit(testing['tweets'])

        # make training vectors
        training['tfidf_vector'] = list(self.vectorizer.transform(training['tweets']).toarray())
        training_vecs = np.vstack(tuple([x for x in training['tfidf_vector'].to_numpy()]))

        # make testing vectors
        athing = self.vectorizer.transform(testing['tweets'])
        print('Number of features (post-processing): {}\n'.format(athing.shape[1]))
        testing['tfidf_vector'] = list(athing.toarray())
        testing_vecs = np.vstack(tuple([x for x in testing['tfidf_vector'].to_numpy()]))

        return training_vecs, testing_vecs

    def runRegression(self, xtrain, xtest):
        regr = linear_model.LinearRegression()
        regr.fit(xtrain, self.ytrain)
        ypred = regr.predict(xtest)

        return ypred

def main(user=None):
    model = VectorComparisonModel(testuser=user)
    train_df, test_df = model.makeDataFrames()
    train_vecs, test_vecs = model.createVectors(train_df, test_df)
    ypred = pd.DataFrame(model.runRegression(train_vecs, test_vecs))

    dist = ((ypred - model.ytest) ** 2).sum(axis=1) ** .5

    final = pd.concat([pd.Series([x for x in model.test_users]),
                       pd.Series(dist)], axis=1)

    final = pd.concat([final, ypred], axis=1, sort=False)

    nonsense = []
    for author, error, s_score, e_score in final.itertuples(index=False):
        nonsense.append(returnNonsense(author, s_score, e_score))

    nonsense = pd.Series(nonsense)
    final = pd.concat([final, nonsense], axis=1, sort=False)

    print('Regression results:')
    pd.set_option('display.max_columns', 5)

    final.columns = ['author_handle', 'model_error',
                     'social_score_estimate', 'economic_score_estimate',
                     'violated_user_bounds']

    if user == None:
        final = final.set_index('author_handle', drop=True)
        print(final[['economic_score_estimate', 'social_score_estimate', 'violated_user_bounds']])

    else:
        from plot_results import plotrunNolans
        print(final[['economic_score_estimate', 'social_score_estimate', 'violated_user_bounds']])
        final.columns = ['author_handle', 'model_error',
                         's_score', 'e_score',
                         'violated_user_bounds']
        plotrunNolans(final[['author_handle','s_score','e_score']],user)

if __name__ == '__main__':
    main('realDonaldTrump')