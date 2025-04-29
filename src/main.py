from pylsl import StreamInlet, resolve_streams, StreamInfo
from time import sleep, time
import numpy as np
import matplotlib.pyplot as plt
from threading import Thread
import sys
from scipy.signal import lfilter, lfilter_zi, firwin
from modules.muse_stream import MuseStream
from modules.constants import LSL_EEG_CHUNK




class LSLViewer:
    def __init__(self, gyro_stream: MuseStream, fig, axes, means):
        self.fig = fig
        self.fig.canvas.mpl_connect("key_press_event", self.OnKeypress)
        self.fig.canvas.mpl_connect("close_event", self.stop_event)
        self.curr_stream = 0
        # * Set the initial rest data
        self.gyro_stream = gyro_stream
        self.gyro_stream.setup_ax(axes)
        self.means = means

        # ? Choose the higher frecunecy
        maxFreq = self.gyro_stream.sfreq
        print("Maxima frecuencia", maxFreq)
        self.display_every = int(0.1 / (12 / 255))
        print("Se muestra cada: ", self.display_every*0.2, "s")
        help_str = """
            toogle full screen : f
            zoom out : /
            zoom in : *
            increase time scale : -
            decrease time scale : +
            """
        print(help_str)

    def OnKeypress(self, event):
        if event.key == "/":
            self.gyro_stream.scale *= 1.2
        elif event.key == "*":
            self.gyro_stream.scale /= 1.2
        elif event.key == "+":
            self.gyro_stream.window += 1
        elif event.key == "-":
            if self.gyro_stream.window > 1:
                self.gyro_stream.window -= 1

    def update_plot(self):
        k = 0
        try:
            while self.started:
                muse_stream = self.gyro_stream
                samples, timestamps = self.gyro_stream.inlet.pull_chunk(timeout=0.1,max_samples=LSL_EEG_CHUNK)
                if timestamps:
                    timestamps = np.float64(np.arange(len(timestamps)))
                    timestamps /= muse_stream.sfreq
                    timestamps += muse_stream.times[-1] + 1.0 / muse_stream.sfreq

                    # muse_stream.times = np.concatenate(
                    #     [muse_stream.times, timestamps]
                    # )
                    muse_stream.n_samples = int(muse_stream.sfreq * muse_stream.window)
                    muse_stream.times = muse_stream.times[
                        -muse_stream.n_samples :
                    ]

                    muse_stream.data = np.vstack([muse_stream.data, samples])
                    muse_stream.data = muse_stream.data[-muse_stream.n_samples :]

                    if k == self.display_every:
                        media = muse_stream.data.mean(axis=0)
                        media = 0
                        plot_data = muse_stream.data - self.means
                        print(f"Mean: {media}")
                        for ii in range(muse_stream.n_chan):
                            if muse_stream.type == "GYRO":
                                print(f"{muse_stream.ch_names[ii]}:", plot_data[-1, ii], end=" ")
                            muse_stream.lines[ii].set_xdata(
                                muse_stream.times[:: muse_stream.subsample]
                                - muse_stream.times[-1]
                            )
                            muse_stream.lines[ii].set_ydata(
                                plot_data[:: muse_stream.subsample, ii] / muse_stream.scale
                                - 0
                            )
                            impedances = np.std(plot_data, axis=0)
                        print("")
                        ticks_labels = [
                            "%s - %.2f" % (muse_stream.ch_names[ii], impedances[ii])
                            for ii in range(muse_stream.n_chan)
                        ]
                        muse_stream.axes.set_yticklabels(ticks_labels)
                        muse_stream.axes.set_xlim(-muse_stream.window, 0)
                        self.fig.canvas.draw()
                        k = 0
                    else:
                        # sleep(0.2)
                        pass
                    k += 1
            print("End")
        except RuntimeError as e:
            raise 

    def start(self):
        self.started = True
        self.thread = Thread(target=self.update_plot)
        self.thread.daemon = True
        self.thread.start()
        plt.show()

    def stop_event(self, close_event):
        self.started = False
        print("Killing all the threads")
        sys.exit()

class Gyro:
    THRESHOLD = 40

    def __init__(self, gyro_stream: MuseStream, ax):
        self.gyro_stream = gyro_stream
        self.gyro_stream.setup_ax(ax)
        self.startef = False    

    def calibrate(self):
        print("Calibrating...")
        time_diff = 0
        data = np.zeros((self.gyro_stream.n_samples, self.gyro_stream.n_chan))
        while (time_diff < 5):
            samples, timestamps = self.gyro_stream.inlet.pull_chunk(timeout=0.5, max_samples=LSL_EEG_CHUNK)
            data = np.vstack([data, samples])
            time_diff += 0.5
        self.mean = np.mean(data, axis=0)
        print("Calibration offset:", self.mean)

    def detect(self):
        self.started = True
        try:
            while self.started:
                muse_stream = self.gyro_stream
                samples, timestamps = self.gyro_stream.inlet.pull_chunk(
                    timeout=0.1, max_samples=LSL_EEG_CHUNK
                )
                if timestamps:
                    timestamps = np.float64(np.arange(len(timestamps)))
                    timestamps /= muse_stream.sfreq
                    timestamps += muse_stream.times[-1] + 1.0 / muse_stream.sfreq

                    muse_stream.n_samples = int(muse_stream.sfreq * muse_stream.window)
                    muse_stream.times = muse_stream.times[-muse_stream.n_samples :]

                    muse_stream.data = np.vstack([muse_stream.data, samples])
                    muse_stream.data = muse_stream.data[-muse_stream.n_samples :]
                    plot_data = muse_stream.data - self.mean

                    for ii in range(muse_stream.n_chan):
                        if muse_stream.type == "GYRO":
                            print(
                                f"{muse_stream.ch_names[ii]}:",
                                plot_data[-1, ii],
                                end=" ",
                            )

                            if ii == 2:
                                print("")
                                # * Select channel Y (1)
                                if plot_data[-1, 1] > self.THRESHOLD:
                                    print("\nPositivo")
                                    sleep(0.3)
                                elif plot_data[-1, 1] < -self.THRESHOLD:
                                    print("\nNegativo")
                                    sleep(0.3)

                        # muse_stream.lines[ii].set_xdata(
                        #     muse_stream.times[:: muse_stream.subsample]
                        #     - muse_stream.times[-1]
                        # )
                        # muse_stream.lines[ii].set_ydata(
                        #     plot_data[:: muse_stream.subsample, ii]
                        #     / muse_stream.scale
                        #     - 0
                        # )
                        # impedances = np.std(plot_data, axis=0)
                        # ticks_labels = [
                        #     "%s - %.2f" % (muse_stream.ch_names[ii], impedances[ii])
                        #     for ii in range(muse_stream.n_chan)
                        # ]
                        # muse_stream.axes.set_yticklabels(ticks_labels)
                        # muse_stream.axes.set_xlim(-muse_stream.window, 0)
                        # self.fig.canvas.draw()
            print("End")
        except RuntimeError as e:
            raise

def plot_data():
    # * Then search for the data that is being streamed
    streams = resolve_streams()

    if (len(streams) == 0):
        raise (RuntimeError("No streams found"))

    gyro_stream: MuseStream = None
    for stream in streams:
        if stream.type() == "GYRO":
            filter = False
            scale = 1
            window = 10
            gyro_stream = MuseStream(stream, filter, scale, window)
            print(gyro_stream)
            print("")

    # * Creating tbe canvas with all the plots we found in the stream
    figure = "15x6"
    figsize = np.int16(figure.split('x'))
    fig, axes = plt.subplots(1, figsize=figsize)
    gyro = Gyro(gyro_stream, axes)
    gyro.calibrate()
    gyro.detect()
    # lsl_viewer = LSLViewer(gyro_stream, fig, axes, gyro.mean)
    # lsl_viewer.start()

plot_data()
