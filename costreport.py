import os,sys
import boto3
import datetime

import model

# For date
from dateutil.relativedelta import relativedelta

class CostExplorer:

    def __init__(self, CurrentMonth=False):
        # Array of reports ready to be output to Excel.
        self.reports = []
        aws_access_key_id=model.get_global_config_value('AWS_ACCESS_KEY_ID') 
        aws_secret_access_key=model.get_global_config_value('AWS_SECRET_ACCESS_KEY')   
        self.client = boto3.client('ce',aws_access_key_id=aws_access_key_id,aws_secret_access_key=aws_secret_access_key)

        self.end = datetime.date.today().replace(day=1)

        self.riend = datetime.date.today()

        if CurrentMonth:
            self.end = self.riend

        self.start = (datetime.date.today() - relativedelta(months=+12))\
            .replace(day=1)  # 1st day of month 12 months ago

        self.ristart = (datetime.date.today() - relativedelta(months=+11))\
            .replace(day=1)  # 1st day of month 11 months ago

        self.sixmonth = (datetime.date.today() - relativedelta(months=+6))\
            .replace(day=1)  # 1st day of month 6 months ago, so RI util has savings values

        try:
            self.accounts = self.getAccounts()
        except:
            self.accounts = {}

    def setStart(self, interval):
        self.start = (datetime.date.today() - relativedelta(months=+interval)).replace(day=1)

    def getAccounts(self):
        accounts = {}
        client = boto3.client('organizations', region_name='us-east-1')
        paginator = client.get_paginator('list_accounts')
        response_iterator = paginator.paginate()
        for response in response_iterator:
            for acc in response['Accounts']:
                accounts[acc['Id']] = acc
        return accounts


    def addReport(self, Name="Default", GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}, ],
                  Style='Total', NoCredits=True, CreditsOnly=False, RefundOnly=False, UpfrontOnly=False,
                  IncSupport=False):

        results = []

        Filter = {
            "Not": {"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Credit", "Refund", "Upfront", "Support"]}}}
        if IncSupport:  # If global set for including support, we dont exclude it
            Filter = {"Not": {"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Credit", "Refund", "Upfront"]}}}

        if CreditsOnly:
            Filter = {"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Credit", ]}}
        if RefundOnly:
            Filter = {"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Refund", ]}}
        if UpfrontOnly:
            Filter = {"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Upfront", ]}}


        response = self.client.get_cost_and_usage(
            TimePeriod={
                'Start': self.start.isoformat(),
                'End': self.end.isoformat()
            },
            Granularity='MONTHLY',
            Metrics=[
                'UnblendedCost',
            ],
            GroupBy=GroupBy,
            Filter=Filter
        )

        if response:
            results.extend(response['ResultsByTime'])
            while 'nextToken' in response:
                nextToken = response['nextToken']
                response = self.client.get_cost_and_usage(
                    TimePeriod={
                        'Start': self.start.isoformat(),
                        'End': self.end.isoformat()
                    },
                    Granularity='MONTHLY',
                    Metrics=[
                        'UnblendedCost',
                    ],
                    GroupBy=GroupBy,
                    NextPageToken=nextToken
                )
                results.extend(response['ResultsByTime'])
                if 'nextToken' in response:
                    nextToken = response['nextToken']
                else:
                    nextToken = False

        rows = []
        sort = ''
        for v in results:
            row = {'date': v['TimePeriod']['Start']}
            sort = v['TimePeriod']['Start']
            for i in v['Groups']:
                key = i['Keys'][0]
                if key in self.accounts:
                    key = self.accounts[key]['Email']
                row.update({key: float(i['Metrics']['UnblendedCost']['Amount'])})

            if not v['Groups']:
                row.update({'Total': float(v['Total']['UnblendedCost']['Amount'])})
            rows.append(row)

        self.reports.append({'Name': Name, 'Data': rows})


def main():
    costexplorer = CostExplorer(CurrentMonth=True)
    costexplorer.setStart(1)
    # Overall Billing Reports
    costexplorer.addReport(Name="Total", GroupBy=[], Style='Total', IncSupport=True)

    # GroupBy Reports
    costexplorer.addReport(Name="Services", GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}], Style='Total', IncSupport=True)

    # print(costexplorer.reports)

if __name__ == '__main__':
    main()