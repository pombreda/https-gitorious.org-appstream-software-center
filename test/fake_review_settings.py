
class FakeReviewSettings(object):
    '''An object that simply holds settings which are used by RatingsAndReviewsAPI
       in the rnrclient_fake module. Using this module allows a developer to test
       the reviews functionality without any interaction with a reviews server.
       Each setting here provides complete control over how the 'server' will 
       respond. Changes to these settings should be made to the class attributes
       directly without creating an instance of this class.
       The intended usage is for unit tests where a predictable response is 
       required and where the application should THINK it has spoken to a 
       server. 
       The unit test would make changes to settings in this class before 
       running the unit test.
    '''

    #server status
    #*****************************
    #raises APIError if True
    server_response_error = False
    
    #review stats
    #*****************************
    #raises APIError if True
    review_stats_error = False    
    
    #the following has no effect if review_stats_error = True
    #determines the number of package stats (i.e. ReviewStats list size) to return
    #max 15 packages (any number higher than 15 will still return 15)
    packages_returned = 3
    
    #get reviews
    #*****************************
    #raises APIError if True
    get_reviews_error= False

    #the following has no effect if get_reviews_error = True
    #determines number of reviews to return (Accepts 0 to n)
    reviews_returned = 1
    
    #get review
    #*****************************
    #raises APIError if True
    get_review_error= False
    
    #flag review
    #*****************************
    #raises APIError if True
    flag_review_error = False
    
    #submit usefulness
    #*****************************
    #raises APIError if True
    submit_usefulness_error = False
    
    #the following has no effect if submit_usefulness_error = True
    #which string to pretend the server returned
    #choices are "Created", "Updated", "Not modified"
    usefulness_response_string = "Created"
    
    #get usefulness
    #*****************************
    #raises APIError if True
    get_usefulness_error = False
