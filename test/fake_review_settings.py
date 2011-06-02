
class FakeReviewSettings(object):
    #server status 
    #*************
    server_response_ok = True     #raises APIError if false
    
    #review stats
    #*************
    review_stats_error = False    #raises APIError if true
    
    #get reviews
    #*************
    get_reviews_error= False   #raises APIError if true

    #the following has no effect if get_reviews_error = True
    reviews_returned = 1       #determines number of reviews to return 
    
    #get review
    #*************
    get_review_error= False   #raises APIError if true
    
    #flag review
    #*************
    flag_review_error = False   #raises APIError if true
    
    #submit usefulness
    #*************
    submit_usefulness_error = False   #raises APIError if true
    
    #get usefulness
        #*************
    get_usefulness_error = False   #raises APIError if true
