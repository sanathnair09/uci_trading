# Trading Script for Prof Schwarz Research

## Preface 

This script was designed to help Prof Schwarz collected data variation in execution times between brokers and other necessary metrics

The script was originally developed by [Alyssa Moncrief](https://www.linkedin.com/in/alyssa-moncrief/) but was redeveloped by [Sanath Nair](https://www.linkedin.com/in/sanathnair09/)

## Getting Started

Make a copy of [.test.env](.test.env) and name it `.env`. Fill in the fields in the env file with the your respective data.

## Running the script

In the [updated_api.py](updated_api.py) file go to the line:

```python 
if __name__ == "__main__"
```
And set the start time, interval between buy and sell, and interval between groups to your liking.

Thats pretty much it. Just monitor the console for error messages and the [previous_program_info.json](previous_program_info.json) file for information about the program as it is running 

**NOTE** - Somtimes the *previous_program_info.json* file may not show the changes immediately in your IDE of choice. Close the file in your IDE and open it again to see the latest changes.
