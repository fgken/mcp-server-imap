import pytest
from unittest.mock import patch, MagicMock
from main import search, dsl_to_search, list_folders

# Test cases for dsl_to_search: (dsl_input, expected_output, test_id)
dsl_test_cases = [
    (
        {"from": "example@example.com"},
        ["FROM", "example@example.com"],
        "from_basic",
    ),
    (
        {"to": "example@example.com"},
        ["TO", "example@example.com"],
        "to_basic",
    ),
    (
        {"subject": "test subject"},
        ["SUBJECT", "test subject"],
        "subject_basic",
    ),
    (
        {"since": "2023-01-15"},
        ["SINCE", "15-Jan-2023"],
        "since_basic",
    ),
    (
        {"before": "2023-01-15"},
        ["BEFORE", "15-Jan-2023"],
        "before_basic",
    ),
    (
        {"from": "sender@example.com", "subject": "important"},
        ["FROM", "sender@example.com", "SUBJECT", "important"],
        "implicit_and",
    ),
    (
        {"or": [{"from": "sender1@example.com"}, {"to": "sender2@example.com"}]},
        [
            "OR",
            "FROM",
            "sender1@example.com",
            "TO",
            "sender2@example.com",
        ],
        "or_operator",
    ),
    (
        {"not": [{"from": "spam@example.com"}]},
        ["NOT", ["FROM", "spam@example.com"]],
        "not_operator_single",
    ),
    (
        {"not": [{"from": "spam@example.com"}, {"subject": "buy now"}]},
        ["NOT", ["FROM", "spam@example.com", "SUBJECT", "buy now"]],
        "not_operator_multiple",
    ),
    (
        {
            "from": "important@example.com",
            "not": [{"subject": "unimportant"}],
            "or": [{"subject": "urgent"}, {"to": "important@example.com"}],
        },
        [
            "FROM",
            "important@example.com",
            "NOT",
            ["SUBJECT", "unimportant"],
            "OR",
            "SUBJECT",
            "urgent",
            "TO",
            "important@example.com",
        ],
        "complex_query",
    ),
    (
        {},
        ["ALL"],
        "empty_criteria",
    ),
    # --- New test cases for parameter combinations ---
    (
        {"since": "2023-01-01", "before": "2023-12-31"},
        ["SINCE", "01-Jan-2023", "BEFORE", "31-Dec-2023"],
        "since_and_before",
    ),
    (
        {"from": "user@example.com", "since": "2024-01-01"},
        ["FROM", "user@example.com", "SINCE", "01-Jan-2024"],
        "from_and_since",
    ),
    (
        {"subject": "meeting", "before": "2024-04-01"},
        ["SUBJECT", "meeting", "BEFORE", "01-Apr-2024"],
        "subject_and_before",
    ),
    (
        {
            "or": [{"from": "a@example.com"}, {"subject": "urgent"}],
            "since": "2024-03-15",
        },
        [
            "SINCE",
            "15-Mar-2024",
            "OR",
            "FROM",
            "a@example.com",
            "SUBJECT",
            "urgent",
        ],
        "or_with_since",
    ),
    (
        {
            "not": [{"from": "spam@example.com"}],
            "before": "2023-01-01",
        },
        [
            "BEFORE",
            "01-Jan-2023",
            "NOT",
            ["FROM", "spam@example.com"],
        ],
        "not_with_before",
    ),
    (
        {
            "from": "boss@example.com",
            "subject": "report",
            "since": "2024-04-10",
            "before": "2024-04-16",
        },
        [
            "FROM",
            "boss@example.com",
            "SUBJECT",
            "report",
            "SINCE",
            "10-Apr-2024",
            "BEFORE",
            "16-Apr-2024",
        ],
        "multiple_conditions_with_date_range",
    ),
]


class TestIMAPSearch:
    @pytest.mark.parametrize("dsl, expected, test_id", dsl_test_cases)
    def test_dsl_to_search_parametrized(self, dsl, expected, test_id):
        """Test dsl_to_search conversion with various inputs."""
        result = dsl_to_search(dsl)
        assert result == expected

    @pytest.mark.asyncio
    @patch("main.IMAPClient")
    async def test_search_function(self, mock_imap_client):
        """Test the search function with mocked IMAPClient"""
        # Setup mock
        mock_client = MagicMock()
        mock_imap_client.return_value.__enter__.return_value = mock_client
        mock_client.search.return_value = [1, 2, 3]

        # Test data
        folder = "INBOX"
        query = {"from": "test@example.com"}

        # Call function without fields parameter (should return only message IDs)
        result = await search(folder, query)

        # Assertions
        mock_client.login.assert_called_once()
        mock_client.select_folder.assert_called_once_with(folder)
        mock_client.search.assert_called_once()
        assert result == {"messages": []}

    @pytest.mark.asyncio
    @patch("main.IMAPClient")
    async def test_search_function_empty_result(self, mock_imap_client):
        """Test the search function with no results"""
        # Setup mock
        mock_client = MagicMock()
        mock_imap_client.return_value.__enter__.return_value = mock_client
        mock_client.search.return_value = []

        # Test data
        folder = "INBOX"
        query = {"from": "nonexistent@example.com"}

        # Call function
        result = await search(folder, query)

        # Assertions
        assert result == {"messages": []}

    @pytest.mark.asyncio
    @patch("main.IMAPClient")
    async def test_search_function_complex_query(self, mock_imap_client):
        """Test the search function with a complex query"""
        # Setup mock
        mock_client = MagicMock()
        mock_imap_client.return_value.__enter__.return_value = mock_client
        mock_client.search.return_value = [10, 20]

        # Test data
        folder = "Archive"
        query = {
            "from": "important@example.com",
            "not": [{"subject": "unimportant"}],
        }

        # Call function
        result = await search(folder, query)

        # Assertions
        mock_client.select_folder.assert_called_once_with(folder)
        assert result == {"messages": []}

    def test_dsl_to_search_empty_query(self):
        """Test conversion of empty query to IMAP search criteria"""
        dsl = {}
        expected = ["ALL"]
        result = dsl_to_search(dsl)
        assert result == expected

    @pytest.mark.asyncio
    @patch("main.IMAPClient")
    async def test_search_function_empty_query(self, mock_imap_client):
        """Test the search function with an empty query object"""
        # Setup mock
        mock_client = MagicMock()
        mock_imap_client.return_value.__enter__.return_value = mock_client
        mock_client.search.return_value = [1, 2, 3, 4, 5]

        # Test data
        folder = "Inbox"
        query = {}

        # Call function
        result = await search(folder, query)

        # Assertions
        mock_client.login.assert_called_once()
        mock_client.select_folder.assert_called_once_with(folder)
        # Verify that search was called with ALL
        mock_client.search.assert_called_once_with(["charset", "UTF-8", "ALL"])
        assert result == {"messages": []}

    @pytest.mark.asyncio
    @patch("main.IMAPClient")
    async def test_search_function_empty_json_string_query(self, mock_imap_client):
        """Test the search function with a query parameter that is an empty JSON string '{}'"""
        # Setup mock
        mock_client = MagicMock()
        mock_imap_client.return_value.__enter__.return_value = mock_client
        mock_client.search.return_value = [101, 102, 103]

        # Test data - this is the specific case requested in the task
        folder = "Inbox"
        query = {}

        # Call function
        result = await search(folder, query)

        # Assertions
        mock_client.login.assert_called_once()
        mock_client.select_folder.assert_called_once_with(folder)
        # Verify that search was called with ALL
        mock_client.search.assert_called_once_with(["charset", "UTF-8", "ALL"])
        assert result == {"messages": []}

    @pytest.mark.asyncio
    @patch("main.IMAPClient")
    async def test_search_function_with_headers(self, mock_imap_client):
        """Test the search function with headers field"""
        # Setup mock
        mock_client = MagicMock()
        mock_imap_client.return_value.__enter__.return_value = mock_client
        mock_client.search.return_value = [1, 2]

        # Mock fetch response with RFC822 data
        mock_client.fetch.return_value = {
            1: {b"RFC822": b"email_content_1"},
            2: {b"RFC822": b"email_content_2"},
        }

        # Mock email message objects
        mock_msg1 = MagicMock()
        mock_msg1.__getitem__.side_effect = lambda x: {
            "From": "sender1@example.com",
            "To": "recipient1@example.com",
            "Subject": "Test Subject 1",
            "Date": "Mon, 10 Apr 2025 10:15:30 +0900",
        }.get(x)
        mock_msg1.__contains__.side_effect = lambda x: x in [
            "From",
            "To",
            "Subject",
            "Date",
        ]

        mock_msg2 = MagicMock()
        mock_msg2.__getitem__.side_effect = lambda x: {
            "From": "sender2@example.com",
            "To": "recipient2@example.com",
            "Subject": "Test Subject 2",
            "Date": "Mon, 10 Apr 2025 11:30:45 +0900",
        }.get(x)
        mock_msg2.__contains__.side_effect = lambda x: x in [
            "From",
            "To",
            "Subject",
            "Date",
        ]

        # Patch email.message_from_bytes to return our mock messages
        with patch("main.email.message_from_bytes", side_effect=[mock_msg1, mock_msg2]):
            # Test data
            folder = "INBOX"
            query = {"from": "test@example.com"}
            fields = {"headers": True}

            # Call function
            result = await search(folder, query, fields)

            # Assertions
            mock_client.login.assert_called_once()
            mock_client.select_folder.assert_called_once_with(folder)
            mock_client.search.assert_called_once()
            mock_client.fetch.assert_called_once()

            # Check the structure of the result
            assert "messages" in result
            assert len(result["messages"]) == 2

            # Check the content of the messages
            assert result["messages"][0]["headers"]["from"] == "sender1@example.com"
            assert result["messages"][0]["headers"]["to"] == "recipient1@example.com"
            assert result["messages"][0]["headers"]["subject"] == "Test Subject 1"
            assert result["messages"][1]["headers"]["from"] == "sender2@example.com"
            assert result["messages"][1]["headers"]["subject"] == "Test Subject 2"

            # Verify that only headers were included
            assert "body" not in result["messages"][0]
            assert "attachments" not in result["messages"][0]

    @pytest.mark.asyncio
    @patch("main.IMAPClient")
    async def test_search_function_with_body(self, mock_imap_client):
        """Test the search function with body field"""
        # Setup mock
        mock_client = MagicMock()
        mock_imap_client.return_value.__enter__.return_value = mock_client
        mock_client.search.return_value = [1]

        # Mock fetch response
        mock_client.fetch.return_value = {1: {b"RFC822": b"email_content"}}

        # Mock email message object
        mock_msg = MagicMock()

        # Patch email.message_from_bytes and get_email_body
        with patch("main.email.message_from_bytes", return_value=mock_msg):
            with patch(
                "main.get_email_body", return_value="This is the email body content"
            ):
                # Test data
                folder = "INBOX"
                query = {"subject": "test"}
                fields = {"body": True}

                # Call function
                result = await search(folder, query, fields)

                # Assertions
                assert "messages" in result
                assert len(result["messages"]) == 1
                assert result["messages"][0]["body"] == "This is the email body content"

                # Verify that only body was included
                assert "headers" not in result["messages"][0]
                assert "attachments" not in result["messages"][0]

    @pytest.mark.asyncio
    @patch("main.IMAPClient")
    async def test_search_function_with_multiple_fields(self, mock_imap_client):
        """Test the search function with multiple fields"""
        # Setup mock
        mock_client = MagicMock()
        mock_imap_client.return_value.__enter__.return_value = mock_client
        mock_client.search.return_value = [1]

        # Mock fetch response with RFC822
        mock_client.fetch.return_value = {1: {b"RFC822": b"email_content"}}

        # Mock email message object
        mock_msg = MagicMock()
        mock_msg.__getitem__.side_effect = lambda x: {
            "From": "sender@example.com",
            "Subject": "Test Subject",
        }.get(x)
        mock_msg.__contains__.side_effect = lambda x: x in ["From", "Subject"]

        # Patch email.message_from_bytes and get_email_body
        with patch("main.email.message_from_bytes", return_value=mock_msg):
            with patch("main.get_email_body", return_value="Email body content"):
                # Test data
                folder = "INBOX"
                query = {"subject": "test"}
                fields = {"headers": True, "body": True}

                # Call function
                result = await search(folder, query, fields)

                # Assertions
                assert "messages" in result
                assert len(result["messages"]) == 1

                # Check that all requested fields are included
                message = result["messages"][0]
                assert "headers" in message
                assert message["headers"]["from"] == "sender@example.com"
                assert message["headers"]["subject"] == "Test Subject"
                assert "body" in message
                assert message["body"] == "Email body content"

    @pytest.mark.asyncio
    @patch("main.time.sleep")
    @patch("main.IMAPClient")
    async def test_search_function_with_throttling(self, mock_imap_client, mock_sleep):
        """Test the search function's throttling functionality for fetch operations"""
        # Setup mock
        mock_client = MagicMock()
        mock_imap_client.return_value.__enter__.return_value = mock_client

        msg_ids = list(range(1, 121))
        mock_client.search.return_value = msg_ids

        # Mock fetch responses
        batch_responses = {}
        for i in range(1, 121):
            batch_responses[i] = {b"RFC822": f"email_content_{i}".encode()}

        def mock_fetch(ids, items):
            response = {}
            for id in ids:
                response[id] = batch_responses[id]
            return response

        mock_client.fetch.side_effect = mock_fetch

        # Mock email message and body
        with patch("main.email.message_from_bytes", return_value=MagicMock()):
            with patch("main.get_email_body", return_value="Email body content"):
                # Test data
                folder = "INBOX"
                query = {"subject": "test"}
                fields = {"headers": True, "body": True}

                # Call function
                result = await search(folder, query, fields)

                # Assertions

                assert (
                    mock_client.fetch.call_count == 3
                )  # 120 messages / 50 per batch = 3 batches

                first_batch_ids = mock_client.fetch.call_args_list[0][0][0]
                assert len(first_batch_ids) == 50
                assert first_batch_ids[0] == 1
                assert first_batch_ids[-1] == 50

                second_batch_ids = mock_client.fetch.call_args_list[1][0][0]
                assert len(second_batch_ids) == 50
                assert second_batch_ids[0] == 51
                assert second_batch_ids[-1] == 100

                # Verify third batch (remaining 20 messages)
                third_batch_ids = mock_client.fetch.call_args_list[2][0][0]
                assert len(third_batch_ids) == 20
                assert third_batch_ids[0] == 101
                assert third_batch_ids[-1] == 120

                assert (
                    mock_sleep.call_count == 2
                )  # Should be called after first and second batches
                assert mock_sleep.call_args_list[0][0][0] == 0.5  # 500ms sleep
                assert mock_sleep.call_args_list[1][0][0] == 0.5  # 500ms sleep

                # Verify all messages were processed
                assert len(result["messages"]) == 120

    @pytest.mark.asyncio
    @patch("main.IMAPClient")
    @patch("main.email.message_from_bytes")
    @patch("main.get_email_body")
    async def test_fetch_multiple_messages(
        self, mock_get_email_body, mock_message_from_bytes, mock_imap_client
    ):
        """Test the fetch function with multiple message IDs"""
        # Setup mocks
        mock_client = MagicMock()
        mock_imap_client.return_value.__enter__.return_value = mock_client

        # Mock responses for each message
        mock_client.fetch.side_effect = [
            {42: {b"RFC822": b"email_content_1"}},
            {43: {b"RFC822": b"email_content_2"}},
        ]

        # Mock email parsing
        mock_message_1 = MagicMock()
        mock_message_2 = MagicMock()
        mock_message_from_bytes.side_effect = [mock_message_1, mock_message_2]

        # Mock email body extraction
        mock_get_email_body.side_effect = ["Email body 1", "Email body 2"]

        # Test data
        message_ids = ["42@INBOX", "43@INBOX"]

        # Import the fetch function
        from main import fetch

        # Call function
        result = fetch(message_ids)

        # Assertions
        assert mock_client.login.call_count == 2
        assert mock_client.select_folder.call_count == 2
        assert mock_client.select_folder.call_args_list[0][0][0] == "INBOX"
        assert mock_client.select_folder.call_args_list[1][0][0] == "INBOX"

        assert mock_client.fetch.call_count == 2
        assert mock_client.fetch.call_args_list[0][0][0] == 42
        assert mock_client.fetch.call_args_list[1][0][0] == 43

        assert mock_message_from_bytes.call_count == 2
        assert mock_get_email_body.call_count == 2

        # Check the result is a dictionary with message IDs as keys
        assert result == {"42@INBOX": "Email body 1", "43@INBOX": "Email body 2"}
