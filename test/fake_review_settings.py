
class FakeReviewSettings(object):
    #server status 
    #*************
    #raises APIError if True
    server_response_error = False
    
    #review stats
    #*************
    #raises APIError if True
    review_stats_error = False    
    
    #the following has no effect if review_stats_error = True
    #determines the number of package stats (i.e. ReviewStats list size) to return
    #max 15 packages (any number higher than 15 will still return 15)
    packages_returned = 3
    
    #get reviews
    #*************
    #raises APIError if True
    get_reviews_error= False

    #the following has no effect if get_reviews_error = True
    #determines number of reviews to return (Accepts 0 to n)
    reviews_returned = 1
    
    #get review
    #*************
    #raises APIError if True
    get_review_error= False
    
    #flag review
    #*************
    #raises APIError if True
    flag_review_error = False
    
    #submit usefulness
    #*************
    #raises APIError if True
    submit_usefulness_error = False
    
    #get usefulness
    #*************
    #raises APIError if True
    get_usefulness_error = False
