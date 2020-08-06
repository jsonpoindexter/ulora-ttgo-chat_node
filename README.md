## MicroPython

#### Build with extra libs
* Use https://github.com/jsonpoindexter/micropython and follow steps for compiling MicroPython for the ESP32

### File Structure
| File      | Description |
| ----------- | ----------- |
| *message_store.py*   | Contains persistent btree / db data stores for nessage objects as well as helper methods  |
| *db.py*      | Contains persistent btree / db data stores for general data such as WEBSERVER_ENABLED |
| *setup_node.py*      | Helper cli to load files onto node |
