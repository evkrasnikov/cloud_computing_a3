

def s3_costs_per_month(num_users):
    # all of these costs are per month
    storage_cost = 0.023 * 200.0/1024 * num_users
    
    request_cost = (20*num_users)/1000.0 * 0.005 + (164 * num_users)/1000*0.0004
    
    total_gb_transfered = 2 * num_users;
    data_transfer_cost = 0
    tier = 0
    tier_cost = [0.0, 0.09,0.085,0.07,0.05]
    tier_limit = [1.0, 10.0*1024, 40.0*1024, 100.0*1024, 9999.0*1024]
    remaining_gb_transfered = total_gb_transfered
    while (remaining_gb_transfered > 0.0001):
        used_gb = min(tier_limit[tier], remaining_gb_transfered)
        data_transfer_cost += used_gb * tier_cost[tier]
        remaining_gb_transfered -= used_gb 
        tier += 1
    
    total_costs = storage_cost + request_cost + data_transfer_cost
    print("S3 costs for {} users, storage {}, request {}, data {}".format(num_users, storage_cost, request_cost, data_transfer_cost))
    print("S3 total cost {}".format(total_costs))


def dynamodb_costs_per_month(num_users):
    read_req_cost = (80*num_users)/1000000.0 * 0.25
    write_req_cost = (8*num_users)/1000000.0 * 1.25

    total_cost = read_req_cost + write_req_cost
    print("dynamodb read cost {}, write cost {}, total cost {} ".format(read_req_cost, write_req_cost, total_cost))

def transcribe_costs_per_month(num_users):
    cost = 180*60*num_users*0.0004
    print("Transcribe cost {} ".format(cost))

def translate_costs_per_month(num_users):
    cost = 119340*num_users*0.000015
    print("Translate cost {} ".format(cost))

def lambda_gateway_costs_per_month(num_users):
    lambda_compute_cost = max(0, 7.5*num_users-400000)*0.00001667
    lambda_requests_cost = max(0, 440.0/1000000 * num_users -1) * 0.2
    gateway_requests_cost = 440.0 * num_users / 1000000
    total_cost =  lambda_compute_cost + lambda_requests_cost + gateway_requests_cost
    print("lambda compute cost {}, request cost {}, gateway cost {}, total {}". format(lambda_compute_cost, lambda_requests_cost, gateway_requests_cost, total_cost))

s3_costs_per_month(1000000)
dynamodb_costs_per_month(1000000)
transcribe_costs_per_month(1000)
translate_costs_per_month(1000)
lambda_gateway_costs_per_month(1000000)
