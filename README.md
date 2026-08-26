# flash-v2

This software is meant for use in corona discharge or materials processing experiments. It provides GUI tools for controlling AC/DC power supplies and for collecting data from a multimeter.

## Installation
Regardless of the installation method, NI-VISA is needed to interface with the instruments.

### As Windows executable
Download the zip file for the desired version from the releases section of the GitHub page. Unzip it to somewhere you will remember. In the destination folder, there will be a `flash-v2.exe` file and a folder called `_internal`. Double click `flash-v2.exe` to run the program. Ignore and do not tamper with `_internal` - it contains necessary internal libraries.

### As Python project
This software is open source and so may be used from source. The [uv](https://docs.astral.sh/uv/) package/project manager is used to manage dependencies. Clone this repository, then cd into `flash-v2/` and run:

```sh
uv run main.py
```
For information on bundling into an executable, see [Packaging](#packaging).
## Usage
Upon launching this program, you will be greeted by the following menu:

![Main launcher menu](doc/launcher.png)

To run a tool, click on the corresponding button. Multiple tools can run at once, and the application will not exit until all windows have been closed.

### AC/DC power supplies

The interfaces for the AC and DC power supply tools are very similar.

![DC flash GUI](doc/dc_flash.png)

![AC flash GUI](doc/ac_flash.png)

### Multimeter

![Multimeter GUI](doc/multimeter.png)

## Architecture
### Flash

```mermaid
sequenceDiagram
    participant G as GUI
    participant C as Control Thread
    participant D as Supply Driver
    participant P as Process Thread
    participant S as Saver Thread

    G->>C: Set Parameters Signal
    C->>D: Set Voltage
    C->>G: Parameters Set Signal
    G->>C: Start Signal
    C->>D: Output Enable
    C->>P: Start
    C->>S: Start
    C->>G: Started Signal

    loop
        P->>D: Set Current
        P->>D: Measure
        D->>P: Supply Data
        P->>S: Sampler Data
        P->>C: Sampler Data
        C->>G: Sampler Data
    end

    G->>C: Stop Signal
    C->>D: Output Disable
    C->>P: Stop Event
    C->>S: Stop Event
    C->>G: Stopped Signal
```
### Multimeter
```mermaid
sequenceDiagram
    participant G as GUI
    participant C as Control Thread
    participant S as Saver Thread
    participant P as Sampler
    participant D as Multimeter Driver

    G->>C: Start Signal
    C->>S: Start
    C->>P: Start
    P->>D: Set Mode

    C->>G: Started Signal

    loop
        P->>D: Measure
        D->>P: Multimeter Data
        P->>S: Multimeter Data
        P->>C: Multimeter Data
        C->>G: Multimeter Data
    end

    G->>C: Stop Signal
    C->>P: Stop Event
    C->>S: Stop Event
    C->>G: Stopped Signal
```

## Packaging
```sh
uv run pyinstaller --windowed --name flash-v2 main.py
```