from pylsl import StreamInlet, resolve_streams, StreamInfo
import muselsl
from time import sleep, time
import numpy as np
import matplotlib.pyplot as plt
from threading import Thread
import sys
from scipy.signal import lfilter, lfilter_zi, firwin

# ---------- CONFIG ----------
SUBSAMPLE = 2
LSL_EEG_CHUNK = 12
# ----------------------------

class MuseStream:
    def __init__(self, stream: StreamInfo, filter: bool, scale: int, window: int):  
        self.stream = stream
        self.inlet = StreamInlet(stream, max_chunklen=LSL_EEG_CHUNK)
        self.info = self.inlet.info()
        description = self.info.desc()
        self.type = stream.type()
        self.sfreq = self.info.nominal_srate()
        self.n_samples = int(self.sfreq * window)
        self.n_chan = self.info.channel_count()
        self.filt = filter
        self.subsample = SUBSAMPLE
        self.scale = scale
        self.window = window

        # * Find the channel names
        ch = description.child("channels").first_child()
        self.ch_names = [ch.child_value("label")]
        for i in range(self.n_chan):
            ch = ch.next_sibling()
            self.ch_names.append(ch.child_value("label"))

    def setup_ax(self, ax):
        # * Set the initial data with only zeros and the channels of information
        self.data = np.zeros((self.n_samples, self.n_chan))
        self.times = np.arange(-self.window, 0, 1. / self.sfreq)
        self.axes = ax
        self.lines = []
        for ii in range(self.n_chan):
            (line,) = self.axes.plot(
                self.times[::SUBSAMPLE], self.data[::SUBSAMPLE, ii] - ii, lw=1
            )
            self.lines.append(line)
        self.axes.set_ylim(-self.n_chan + 0.5, 0.5)
        ticks = np.arange(0, -self.n_chan, -1)
        self.impedances = np.std(self.data, axis=0)
        ticks_labels = [
            "%s - %.1f" % (self.ch_names[ii], self.impedances[ii]) for ii in range(self.n_chan)
        ]

        self.bf, self.af, self.filt_state, self.data_f = None, None, None, None
        if (self.type == "EEG"):
            self.bf = firwin(
                32, np.array([1, 40]) / (self.sfreq / 2.0), width=0.05, pass_zero=False
            )
            self.af = [1.0]
            zi = lfilter_zi(self.bf, self.af)
            self.filt_state = np.tile(zi, (self.n_chan, 1)).transpose()
            self.data_f = np.zeros((self.n_samples, self.n_chan))

        ax.set_yticklabels(ticks_labels)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel(self.type)
        ax.xaxis.grid(False)
        ax.set_yticks(ticks)

    def __str__(self):
        message = f"""Stream info [{self.type}]:
        Nominal frecuency: {self.sfreq} Hz
        Number of samples: {self.n_samples}
        Number of channels: {self.n_chan}
        Channels: {self.ch_names}
        """
        return message

class LSLViewer:
    def __init__(self, streams: list[MuseStream], fig, axes):
        self.fig = fig
        self.fig.canvas.mpl_connect("key_press_event", self.OnKeypress)
        self.fig.canvas.mpl_connect("close_event", self.stop_event)
        self.streams = streams
        self.curr_stream = 0
        # * Set the initial rest data
        for i in range(len(self.streams)):
            streams[i].setup_ax(axes[i])
            if (streams[i].type == "EEG"):
                self.eeg_stream = streams[i]
                self.ax_eeg = axes[i]    

        # ? Choose the higher frecunecy
        maxFreq = max(list(map(lambda x: x.sfreq, self.streams)))
        print("Maxima frecuencia", maxFreq)
        self.display_every = int(0.1 / (12 / maxFreq))
        print("Se muestra cada: ", self.display_every*0.2, "s")
        help_str = """
            toggle filter : d
            toogle full screen : f
            zoom out : /
            zoom in : *
            increase time scale : -
            decrease time scale : +
            change stream backward: <-
            change stream forward: ->
            """
        print(help_str)

    def OnKeypress(self, event):
        if event.key == "/":
            self.streams[self.curr_stream].scale *= 1.2
        elif event.key == "*":
            self.streams[self.curr_stream].scale /= 1.2
        elif event.key == "+":
            self.streams[self.curr_stream].window += 1
        elif event.key == "-":
            if self.streams[self.curr_stream].window > 1:
                self.streams[self.curr_stream].window -= 1
        elif event.key == "d":
            if (self.eeg_stream):
                self.eeg_stream.filt = not (self.eeg_stream.filt)
                print("Filter toggled")
            else:
                print("There' no EEG signal")
        elif event.key == "left":
            if self.curr_stream > 0:
                self.curr_stream -= 1
            else:
                self.curr_stream = len(self.streams) - 1
            print("You're at", self.streams[self.curr_stream].type)
        elif event.key == "right":
            if self.curr_stream < len(self.streams) - 1:
                self.curr_stream += 1
            else:
                self.curr_stream = 0
            print("You're at", self.streams[self.curr_stream].type)

    def update_plot(self):
        k = 0
        try:
            while self.started:
                for i in range(len(self.streams)):
                    muse_stream = self.streams[i]
                    samples, timestamps = muse_stream.inlet.pull_chunk(timeout=0.1,max_samples=LSL_EEG_CHUNK)
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
                        if muse_stream.type == "EEG" and muse_stream.filt:
                            filt_samples, muse_stream.filt_state = lfilter(
                                muse_stream.bf,
                                muse_stream.af,
                                samples,
                                axis=0,
                                zi=muse_stream.filt_state,
                            )
                            muse_stream.data_f = np.vstack(
                                [muse_stream.data_f, filt_samples]
                            )
                            muse_stream.data_f = muse_stream.data_f[
                                -muse_stream.n_samples :
                            ]
                        if k == self.display_every:
                            if muse_stream.filt and muse_stream.type == "EEG":
                                plot_data = muse_stream.data_f
                            elif not muse_stream.filt:
                                plot_data = muse_stream.data - muse_stream.data.mean(
                                    axis=0
                                )
                            for ii in range(muse_stream.n_chan):
                                if muse_stream.type == "ACC":
                                    print(f"{muse_stream.ch_names[ii]}:", plot_data[-1, ii], end="")
                                muse_stream.lines[ii].set_xdata(
                                    muse_stream.times[:: muse_stream.subsample]
                                    - muse_stream.times[-1]
                                )
                                muse_stream.lines[ii].set_ydata(
                                    plot_data[:: muse_stream.subsample, ii] / muse_stream.scale
                                    - ii
                                )
                                impedances = np.std(plot_data, axis=0)
                            print("")
                            ticks_labels = [
                                "%s - %.2f" % (muse_stream.ch_names[ii], impedances[ii])
                                for ii in range(muse_stream.n_chan)
                            ]
                            muse_stream.axes.set_yticklabels(ticks_labels)
                            muse_stream.axes.set_xlim(-muse_stream.window, 0)
                    else:
                        # sleep(0.2)
                        pass

                    if k == self.display_every:
                        self.fig.canvas.draw()
                        k = 0
                    k += 1
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

def plot_data():
    # * Then search for the data that is being streamed
    print("Buscando stream EEG...")
    streams = resolve_streams()

    if (len(streams) == 0):
        raise (RuntimeError("No streams found"))

    muse_streams: list[MuseStream] = []
    for stream in streams:
        if stream.type() == "EEG": 
            filter = True
            scale = 100
            window = 1
        else: 
            filter = False
            if stream.type() == "ACC":
                scale = 5
            elif stream.type() == "GYRO":
                scale = 20
            else:
                scale = 20
            window = 10
        muse_stream = MuseStream(stream, filter, scale, window)
        muse_streams.append(muse_stream)
        print(muse_stream)
        print("")

    # * Creating tbe canvas with all the plots we found in the stream
    n_streams = len(muse_streams)
    figure = "15x6"
    figsize = np.int16(figure.split('x'))
    fig, axes = plt.subplots(1, n_streams, figsize=figsize)
    lsl_viewer = LSLViewer(muse_streams, fig, axes)
    lsl_viewer.start()

plot_data()
# # * Define multiple threads for the streaming and the viewing
# thread = Thread(target=plot_data)
# thread.daemon = True

# # * Start first the muse streaming
# muses = muselsl.list_muses()
# if len(muses) == 0:
#     raise RuntimeError("No muses found")
# for muse in muses:
#     print(f"Muse {muse["address"]}")
# thread.start()
# muselsl.stream(muses[0]["address"], acc_enabled=True, gyro_enabled=True)
