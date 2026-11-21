import json
import os
import unittest
from unittest.mock import MagicMock, patch
from starlette.testclient import TestClient
import server

TOKEN = 'a' * 48

class ServerTests(unittest.TestCase):
    def test_fail_closed_without_token(self):
        with patch.dict(os.environ, {'MCP_BEARER_TOKEN': ''}):
            with self.assertRaises(RuntimeError): server.create_app()
    def test_bearer_auth_and_mcp_tool_discovery(self):
        with patch.dict(os.environ, {'MCP_BEARER_TOKEN': TOKEN}):
            app = server.create_app()
            with TestClient(app, base_url='http://localhost:8000') as client:
                headers = {'Accept': 'application/json, text/event-stream', 'Content-Type': 'application/json'}
                msg = {'jsonrpc':'2.0','id':1,'method':'tools/list','params':{}}
                self.assertEqual(client.post('/mcp', json=msg, headers=headers).status_code, 401)
                self.assertEqual(client.post('/mcp', json=msg, headers={**headers,'Authorization':'Bearer wrong'}).status_code, 401)
                response = client.post('/mcp', json=msg, headers={**headers,'Authorization':'Bearer '+TOKEN})
                self.assertEqual(response.status_code, 200, response.text)
                names = {t['name'] for t in response.json()['result']['tools']}
                self.assertEqual(names, {'channel_info','list_uploads','video_details','channel_analytics','audience_retention'})
    def test_input_validation(self):
        for value in ['bad', 'a'*11 + ',abc', '../secrets']:
            with self.assertRaises(ValueError): server.valid_video(value)
        with self.assertRaises(ValueError): server.valid_dates('2024-02-02','2024-01-01')
        with self.assertRaises(ValueError): server.list_uploads(51)
        with self.assertRaises(ValueError): server.video_details([])
    @patch('server.service')
    def test_channel_analytics_sends_supported_query(self, service):
        service.return_value.reports.return_value.query.return_value.execute.return_value = {'rows': [['abc', 42]]}
        result = server.channel_analytics('2024-01-01','2024-02-01','video',25)
        self.assertEqual(result['rows'][0][1],42)
        kwargs = service.return_value.reports.return_value.query.call_args.kwargs
        self.assertEqual(kwargs['ids'],'channel==MINE')
        self.assertNotIn('impressions',kwargs['metrics'])
    @patch('server.service')
    def test_retention_is_video_filtered(self, service):
        service.return_value.reports.return_value.query.return_value.execute.return_value = {'rows': []}
        server.audience_retention('78x-PmvyARk','2024-01-01','2024-02-01')
        args = service.return_value.reports.return_value.query.call_args.kwargs
        self.assertEqual(args['filters'],'video==78x-PmvyARk')
        self.assertEqual(args['dimensions'],'elapsedVideoTimeRatio')
    @patch('server.service')
    def test_uploads_pagination(self, service):
        api = service.return_value
        api.channels.return_value.list.return_value.execute.return_value = {'items':[{'contentDetails':{'relatedPlaylists':{'uploads':'uploads123'}}}]}
        api.playlistItems.return_value.list.return_value.execute.return_value = {'items':[], 'nextPageToken':'next'}
        self.assertEqual(server.list_uploads(5, 'previous')['nextPageToken'], 'next')
        self.assertEqual(api.playlistItems.return_value.list.call_args.kwargs['pageToken'], 'previous')

if __name__ == '__main__': unittest.main()
