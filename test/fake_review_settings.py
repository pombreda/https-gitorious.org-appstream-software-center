
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
    
    #general settings
    #*****************************
    #delay (in seconds) before returning from any of the fake rnr methods
    #useful for emulating real network timings (use None for no delays)
    fake_network_delay = None

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
    
    #submit review
    #*****************************
    #raises APIError if True
    submit_review_error = False
    #fake username(str) and review_id(int) to give back with a successful review
    #leave as None to generate a random username and review_id
    reviewer_username = None
    submit_review_id = None
    
    #flag review
    #*****************************
    #raises APIError if True
    flag_review_error = False
    #fake username(str) to give back as 'flagger'
    flagger_username = None
    #fake package name (str) to give back as flagged app
    flag_package_name = None
    
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
    
    #the following has no effect if get_usefulness_error = True
    #how many usefulness votes to return
    votes_returned = 5
    
    #pre-configured review ids to return in the result 
    #if you don't complete this or enter less review ids than votes_returned
    #above, it will be random
    required_review_ids = [3,6,15]
    
    #THE FOLLOWING SETTINGS RELATE TO LOGIN SSO FUNCTIONALITY
    # LoginBackendDbusSSO
    # login()
    #***********************
    # what to fake the login response as 
    # choices (strings): "successful", "failed", "denied"
    login_response = "successful"
