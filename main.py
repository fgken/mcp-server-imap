import argparse
import os
import time
from mcp.server.fastmcp import FastMCP
from imapclient import IMAPClient
import email
from email import policy
from datetime import datetime

IMAP_SERVER = ""
IMAP_PORT = 0
IMAP_USER = ""
IMAP_PASSWORD = ""
IMAP_USE_STARTTLS = ""

# Initialize FastMCP server
mcp = FastMCP("imap")


def get_email_body(msg):
    text_part = None
    html_part = None

    for part in msg.walk():
        content_type = part.get_content_type()
        content_disposition = str(part.get("Content-Disposition", "")).lower()

        if "attachment" in content_disposition:
            continue

        if content_type == "text/plain" and text_part is None:
            text_part = part.get_payload(decode=True).decode(
                part.get_content_charset() or "utf-8", errors="replace"
            )

        elif content_type == "text/html" and html_part is None:
            html_part = part.get_payload(decode=True).decode(
                part.get_content_charset() or "utf-8", errors="replace"
            )

    return text_part or html_part or ""


def dsl_to_search(dsl: dict) -> list:
    def format_date(date_str):
        """'YYYY-MM-DD' → 'D-Mon-YYYY'"""
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d-%b-%Y")

    def parse_condition(cond):
        if "from" in cond:
            return ["FROM", cond["from"]]
        if "to" in cond:
            return ["TO", cond["to"]]
        if "cc" in cond:
            return ["CC", cond["cc"]]
        if "subject" in cond:
            return ["SUBJECT", cond["subject"]]
        if "since" in cond:
            return ["SINCE", format_date(cond["since"])]
        if "before" in cond:
            return ["BEFORE", format_date(cond["before"])]
        return []

    def parse_criteria(criteria):
        result = []

        # Handle regular conditions first
        for key, value in criteria.items():
            if key not in ["or", "not"]:
                # Create a single-key dictionary for each condition
                single_condition = {key: value}
                result.extend(parse_condition(single_condition))

        # Handle logical operators
        if "not" in criteria:
            # For multiple conditions in 'not', we use IMAPClient's nested criteria list feature
            # NOT (cond1 OR cond2 OR ...) is equivalent to NOT cond1 AND NOT cond2 AND ...
            not_criteria = criteria["not"]
            if isinstance(not_criteria, list):
                # Create a list of all conditions in the 'not' operator
                not_conditions = []
                for condition in not_criteria:
                    not_conditions.extend(parse_criteria(condition))

                # Add the NOT operator with the nested conditions
                if not_conditions:
                    result.extend(["NOT", not_conditions])

        if "or" in criteria:
            # Handle 'or' as a list of conditions
            if isinstance(criteria["or"], list):
                or_conditions = []
                for condition in criteria["or"]:
                    or_conditions.append(parse_criteria(condition))

                # Combine all conditions with OR
                if len(or_conditions) >= 2:
                    # Start with the first two conditions
                    result.extend(["OR"] + or_conditions[0] + or_conditions[1])

                    # Add additional conditions if present
                    for i in range(2, len(or_conditions)):
                        result = ["OR"] + result + or_conditions[i]

        # If it's a single condition with no logical operators
        if len(result) == 0 and isinstance(criteria, dict):
            return parse_condition(criteria)

        return result

    # 実行
    search_criteria = parse_criteria(dsl)

    if len(search_criteria) == 0:
        search_criteria.append("ALL")

    return search_criteria


@mcp.tool()
def list_folders() -> list:
    """Get a list of IMAP folders."""

    with IMAPClient(
        host=IMAP_SERVER, port=IMAP_PORT, ssl=not IMAP_USE_STARTTLS
    ) as client:
        if IMAP_USE_STARTTLS:
            client.starttls()
        client.login(IMAP_USER, IMAP_PASSWORD)
        folders = client.list_folders()

        # Convert folder tuples to dictionaries
        folder_list = []
        for _, _, name in folders:
            folder_list.append(name)

        return folder_list


@mcp.tool()
async def search(folder: str, criteria: dict, fields: dict = None) -> dict:
    """Search for emails in the specified IMAP folder and fetch selected components.

    DESCRIPTION:
        This function performs an IMAP search operation using the provided query criteria
        and returns matching email messages with requested components (headers, body).
        The search criteria support logical operations and various email attributes.

    PARAMETERS:
        folder: str
            Name of the IMAP folder to search in (e.g., "INBOX", "Sent", "Drafts").
            Must be a valid folder name on the connected IMAP server.

        criteria: dict
            JSON-formatted search criteria with the following structure:
            {
                # Logical operators (optional):
                "or": [                              # ANY condition must match
                    {<condition>},
                    {<condition>}
                    # ... more conditions
                ],
                "not": [                             # Negates multiple conditions
                    {<condition1>},
                    {<condition2>}
                    # ... multiple conditions are treated as NOT <condition1> AND NOT <condition2>
                ],

                # Search conditions (optional, multiple keys = AND):
                "from": "string",             # Sender email/name contains this string
                "to": "string",               # Recipient email/name contains this string
                "cc": "string",               # CC recipient contains this string
                "subject": "string",          # Subject line contains this string
                "since": "YYYY-MM-DD",        # Format: "YYYY-MM-DD", date on/after
                "before": "YYYY-MM-DD",       # Format: "YYYY-MM-DD", date before
            }
            If criteria is empty or missing, matches ALL messages in the folder.

        fields: dict, optional
            Specifies which components to include in the results:
            {
                "headers": bool,  # Include email headers (From, To, Cc, Subject, Date)
                "body": bool,     # Include email body text
            }
            If None or empty, an empty messages list is returned.

    RETURNS:
        dict
            A dictionary with the following structure:
            {
                "messages": [          # List of message data dictionaries
                    {
                        "id": str,            # Message ID as "id@folder"
                        "headers": {          # Present if headers requested
                            "from": str,
                            "to": str,
                            "cc": str,
                            "subject": str,
                            "date": str,
                            "message-id": str
                        },
                        "body": str           # Present if body requested
                    },
                    # ... more messages
                ]
            }
            If no messages match or fields is empty, "messages" will be an empty list.

    BEHAVIOR NOTES:
        - String searches are case-insensitive and match substrings
        - Multiple criteria at the same level are combined with AND logic
        - Logical operators can be nested for complex queries

    EXAMPLES:
        # Search for emails from alice OR bob since 2023-01-01
        criteria = {
            "or": [
                {"from": "alice"},
                {"from": "bob"}
            ],
            "since": "2023-01-01"
        }
    """

    # Default fields if not provided
    if fields is None:
        fields = {}

    # Determine what to fetch
    fetch_headers = fields.get("headers", False)
    fetch_body = fields.get("body", False)

    # Check if we need to fetch email data
    fetch_email_data = fetch_headers or fetch_body

    search_criteria = ["charset", "UTF-8"] + dsl_to_search(criteria)

    try:
        await mcp.get_context().request_context.session.send_log_message(
            "debug", search_criteria
        )
    except Exception:
        pass  # for unit test

    with IMAPClient(
        host=IMAP_SERVER, port=IMAP_PORT, ssl=not IMAP_USE_STARTTLS
    ) as client:
        if IMAP_USE_STARTTLS:
            client.starttls()
        client.login(IMAP_USER, IMAP_PASSWORD)
        client.select_folder(folder)

        msg_ids = client.search(search_criteria)

        # If no fields requested or no messages found, just return empty messages list
        if not fetch_email_data or not msg_ids:
            return {"messages": []}

        # Determine what to fetch based on requested fields
        fetch_items = []

        if fetch_headers or fetch_body:
            fetch_items.append(
                "RFC822"
            )  # Fetch the full message if any content is needed

        # Fetch the requested data for all messages
        messages = []

        BATCH_SIZE = 50
        SLEEP_TIME = 0.5  # seconds

        resp = {}
        for i in range(0, len(msg_ids), BATCH_SIZE):
            batch_ids = msg_ids[i : i + BATCH_SIZE]
            batch_resp = client.fetch(batch_ids, fetch_items)
            resp.update(batch_resp)

            if i + BATCH_SIZE < len(msg_ids):
                time.sleep(SLEEP_TIME)

        for id in msg_ids:
            message_data = {"id": f"{id}@{folder}"}

            # Process email content if needed
            if fetch_headers or fetch_body:
                raw_email = resp[id][b"RFC822"]
                msg = email.message_from_bytes(raw_email, policy=policy.default)

                # Extract headers if requested
                if fetch_headers:
                    headers = {}
                    for header in ["From", "To", "Cc", "Subject", "Date", "Message-ID"]:
                        if header in msg:
                            headers[header.lower()] = str(msg[header])
                    message_data["headers"] = headers

                # Extract body if requested
                if fetch_body:
                    message_data["body"] = get_email_body(msg)

            messages.append(message_data)

        # Return only message data
        return {"messages": messages}


@mcp.tool()
def fetch(message_ids: list) -> dict:
    """Get the bodies of emails associated with message ids

    INPUT:
    message_ids: list - List of message IDs (e.g., ["42@INBOX", "43@INBOX"])

    OUTPUT:
    dict - Dictionary where keys are message IDs and values are the corresponding email bodies
    """
    results = {}

    for message_id in message_ids:
        id, folder = message_id.split("@", 1)
        with IMAPClient(
            host=IMAP_SERVER, port=IMAP_PORT, ssl=not IMAP_USE_STARTTLS
        ) as client:
            if IMAP_USE_STARTTLS:
                client.starttls()
            client.login(IMAP_USER, IMAP_PASSWORD)
            client.select_folder(folder)
            resp = client.fetch(int(id), ["RFC822"])
            raw_email = resp[int(id)][b"RFC822"]
            msg = email.message_from_bytes(raw_email, policy=policy.default)
            body = get_email_body(msg)
            results[message_id] = body

    return results


# Parse command-line arguments when run directly
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IMAP MCP Server")
    parser.add_argument("--server", help="IMAP server hostname")
    parser.add_argument(
        "--port",
        type=int,
        help="IMAP server port (default: 993 for TLS, 143 for STARTTLS)",
    )
    parser.add_argument("--user", help="IMAP username (can also use IMAP_USER env var)")
    parser.add_argument(
        "--password", help="IMAP password (can also use IMAP_PASSWORD env var)"
    )
    parser.add_argument(
        "--use-starttls", action="store_true", help="Use STARTTLS instead of direct TLS"
    )

    args = parser.parse_args()

    # Update IMAP connection settings from command-line arguments or environment variables
    IMAP_SERVER = args.server
    IMAP_PORT = args.port

    # Prioritize command-line arguments over environment variables
    IMAP_USER = args.user if args.user is not None else os.environ.get("IMAP_USER", "")
    IMAP_PASSWORD = (
        args.password
        if args.password is not None
        else os.environ.get("IMAP_PASSWORD", "")
    )

    IMAP_USE_STARTTLS = args.use_starttls

    # Initialize and run the server
    mcp.run(transport="stdio")
