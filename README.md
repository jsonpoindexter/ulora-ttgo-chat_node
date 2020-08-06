## MicroPython

#### Build with extra libs
* Use https://github.com/jsonpoindexter/micropython and follow steps for compiling MicroPython for the ESP32

### File Structure
| File      | Description |
| ----------- | ----------- |
| *lora.py*   | Contains lora initialization. ***NOTE*** this should be run first as it has the possibility to cause a restart  |
| *db.py*      | Contains persistent btree / db data stores for messageObj array and WEBSERVER_ENABLED |
| *setup_node.py*      | Helper cli to load files onto node |
