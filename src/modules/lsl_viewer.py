import matplotlib.pyplot as plt
from threading import Thread
from modules.muse_stream import MuseStream
from modules.constants import *
import numpy as np
import sys
from scipy.signal import lfilter, lfilter_zi, firwin

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
        print("Se muestra cada: ", self.display_every * 0.2, "s")
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
                samples, timestamps = self.gyro_stream.inlet.pull_chunk(
                    timeout=0.1, max_samples=LSL_EEG_CHUNK
                )
                if timestamps:
                    timestamps = np.float64(np.arange(len(timestamps)))
                    timestamps /= muse_stream.sfreq
                    timestamps += muse_stream.times[-1] + 1.0 / muse_stream.sfreq

                    # muse_stream.times = np.concatenate(
                    #     [muse_stream.times, timestamps]
                    # )
                    muse_stream.n_samples = int(muse_stream.sfreq * muse_stream.window)
                    muse_stream.times = muse_stream.times[-muse_stream.n_samples :]

                    muse_stream.data = np.vstack([muse_stream.data, samples])
                    muse_stream.data = muse_stream.data[-muse_stream.n_samples :]

                    if k == self.display_every:
                        media = muse_stream.data.mean(axis=0)
                        media = 0
                        plot_data = muse_stream.data - self.means
                        print(f"Mean: {media}")
                        for ii in range(muse_stream.n_chan):
                            if muse_stream.type == "GYRO":
                                print(
                                    f"{muse_stream.ch_names[ii]}:",
                                    plot_data[-1, ii],
                                    end=" ",
                                )
                            muse_stream.lines[ii].set_xdata(
                                muse_stream.times[:: muse_stream.subsample]
                                - muse_stream.times[-1]
                            )
                            muse_stream.lines[ii].set_ydata(
                                plot_data[:: muse_stream.subsample, ii]
                                / muse_stream.scale
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
