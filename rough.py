from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate
import os
from dotenv import load_dotenv
import pandas as pd
load_dotenv()  # Loads variables from .env into the environment

# Now get the OPENAI_API_KEY from environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")

# Instantiate the OpenAI model (adjust temperature and model_name as needed)
model = ChatOpenAI(temperature=0, model_name="gpt-4o-mini", openai_api_key=openai_api_key)

JOB_POSTING_EXTRACTION_TEMPLATE = (
    "You are tasked with extracting the job postings from the following text: {dom_content}. "
    "Return the job postings in a valid JSON list format. Each job posting should be an object with "
    "the following keys if present: 'title', 'location', 'description', and any other relevant info. "
    "If there are no job postings, return an empty JSON list: []"
)

def extract_job_postings(dom_chunks):
    """
    Given a list of DOM (markdown) chunks, uses the OpenAI API to extract job postings
    as a JSON list of objects: [{"title": "...", "location": "...", ...}, ...].
    Returns a concatenated list of job posting dictionaries.
    """
    prompt = ChatPromptTemplate.from_template(JOB_POSTING_EXTRACTION_TEMPLATE)
    chain = LLMChain(llm=model, prompt=prompt)

    all_postings = []
    for chunk in dom_chunks:
        print("chunk:\n", chunk)
        response = chain.run({"dom_content": chunk})
        print(response)
        try:
            postings = pd.io.json.loads(response)
            if isinstance(postings, dict):
                postings = [postings]
            if isinstance(postings, list):
                all_postings.extend(postings)
        except Exception:
            # If the output isn't valid JSON, you can log or handle the error as needed.
            pass

    return all_postings

dom_chunk = """ Title: Investec Careers

URL Source: https://careers.investec.co.za/jobs/vacancy/external-consultant---business-transactional-banking-11331-sandton/11349/description/

Markdown Content:
[](https://careers.investec.co.za/jobs/home/ "Home")[Search & Apply](https://careers.investec.co.za/jobs/vacancy/find/results/action/posbrowser_resetto/?pagestamp=eece8c87-77dc-4ea5-bc96-c67f9f2a6d4a "Search & Apply") Job description

Job description
---------------

*   Location:

    Sandton

*   Employee Type:

    Permanent

*   Department:

    Business Transactional Banking

*   Division:

    Investec Corporate And Institutional Banking


External Consultant - Business Transactional Banking (11331)
------------------------------------------------------------

**Description**

The External Consultant will be responsible for the acquisition of new business clients as well as the maintenance of existing clients. In partnership with an Internal Consultant deliver an exceptional client service to business clients, and being a connector and an “enabler” for clients' needs into the other divisions of the Investec Group, for example, Investec For Business, Private Bank and Investec Wealth & Investment.

**This would involve:**

**Sales and Relationship Management:** 
•    Marketing and sales of all Business Banking products across lending, cash, forex and transactional as per allocated budget.    
•    Develop strong relationships with key stakeholders in the Group to acquire/convert clients (Investec for Business, Coverage, Private Banking, and Treasury Sales and Structuring). 
•    Identifying clients' needs, presenting and implementing these solutions, as well as enabling clients to utilize our digital platforms (online and mobile). 
•    Driving proactive client contact and managing client expectations. 
•    Attending deal/ credit forums with lending product areas when required.
•    Entertaining of key or potential clients at Investec events.

**Product knowledge:** 
•    In-depth understanding of Transactional Banking (Card acquiring, Debit Order collections service, Host to Host, e-Commerce, Forex, Cash Investments).
•    The incumbent will need to drive product cross-sell and utilization. 
•    Good understanding and interpretation of Financial Statements.

The incumbent would need to have a Commerce Degree, and/or FAIS accreditation, with 3 – 5 years' financial services experience in a frontline/similar role.

**Investec Culture**

At Investec we look for dynamic, energetic people filled with tenacity, integrity and out of the ordinary thinking.

We value individuals who in turn value our [culture](https://www.investec.com/en_za/welcome-to-investec/Careers.html) that is, a can-do attitude while challenging convention.

Diversity, competency, and flexible leadership are respected in pursuit of the growth of our business.

We are committed to diversity and inclusion when recruiting internally and externally.


 

*   [Apply Now](https://careers.investec.co.za/jobs/vacancy/external-consultant---business-transactional-banking-11331-sandton/11349/description/action/apply/?pagestamp=eece8c87-77dc-4ea5-bc96-c67f9f2a6d4a "Apply now")

Close map

100 Grayston Drive, Sandown, Sandton, South Africa, 2196

*   [Apply Now](https://careers.investec.co.za/jobs/vacancy/external-consultant---business-transactional-banking-11331-sandton/11349/description/action/apply/?pagestamp=eece8c87-77dc-4ea5-bc96-c67f9f2a6d4a "Apply now")

Meet the recruiter
------------------

Fikile Mthimkulu

LinkedIn

Create an alert subscription based on this vacancy

*   [Create Alert](https://careers.investec.co.za/jobs/vacancy/11349/alerts/ "Alerts")

Benefits
--------

Pension

Private Medical Cover

Virtual GP

Gym Discounts

Psychologist Service

Annual Leave

Life Assurance"""

# Extract the job postings from the DOM chunk
print(extract_job_postings(dom_chunk))