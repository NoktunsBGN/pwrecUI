#!/usr/bin/env python3
#   pwrecUI - A simple GTK3 GUI for pw-record using Python 3
#
#   Copyright (C) 2026 Slavi Slavchev

#   This program is free software; you can redistribute it and/or modify it
#   under the terms of the GNU General Public License as published by the Free
#   Software Foundation; either version 2 of the License, or (at your option)
#   any later version.

#   This program is distributed in the hope that it will be useful, but WITHOUT
#   ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
#   FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
#   more details.

#   You should have received a copy of the GNU General Public License along
#   with this program; if not, write to the Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


import os
import signal
import subprocess
import sys
import time
import random
from datetime import datetime

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib


def format_seconds(total):
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60

    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def human_size(num_bytes):
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    return f"{num_bytes / (1024 * 1024 * 1024):.1f} GB"


def default_filename():
    timestamp = datetime.now().strftime("%d-%m-%y-%H-%M")
    rand_num = random.randint(100000000, 999999999)
    return os.path.expanduser(f"~/vrec-{timestamp}-{rand_num}.wav")


class VoiceRecorderWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Voice Recorder")
        self.set_border_width(16)
        self.set_default_size(560, 180)
        self.set_resizable(False)

        self.proc = None
        self.recording = False
        self.output_file = ""
        self.start_time = None
        self.timer_id = None

        self.connect("delete-event", self.on_delete_event)

        self.outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add(self.outer_box)

        self.build_file_selection_ui()

    def clear_ui(self):
        for child in self.outer_box.get_children():
            self.outer_box.remove(child)

    def build_file_selection_ui(self):
        self.clear_ui()

        self.output_file = default_filename()

        row1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.outer_box.pack_start(row1, True, True, 0)

        label = Gtk.Label(label="Output file:")
        label.set_xalign(0)
        row1.pack_start(label, False, False, 0)

        path_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row1.pack_start(path_row, False, False, 0)

        self.path_entry = Gtk.Entry()
        self.path_entry.set_text(self.output_file)
        self.path_entry.set_hexpand(True)
        path_row.pack_start(self.path_entry, True, True, 0)

        browse_button = Gtk.Button(label="Browse")
        browse_button.connect("clicked", self.on_browse_clicked)
        path_row.pack_start(browse_button, False, False, 0)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.outer_box.pack_end(buttons, False, False, 0)

        ok_button = Gtk.Button(label="OK")
        ok_button.connect("clicked", self.on_file_ok_clicked)
        buttons.pack_end(ok_button, False, False, 0)

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda *_: Gtk.main_quit())
        buttons.pack_end(cancel_button, False, False, 0)

        footer = Gtk.Label()
        footer.set_use_markup(True)
        footer.set_line_wrap(True)
        footer.set_justify(Gtk.Justification.CENTER)

        footer.set_markup(
            "<span size='x-small'>"
            "pwrecUI version 1.0, Copyright (C) 2026 Slavi Slavchev.\n"
            "pwrecUI comes with ABSOLUTELY NO WARRANTY; This is free software, "
            "and you are welcome to redistribute it under certain conditions as "
            "defined by the GPL-2.0 license included with this program."
            "</span>"
        )

        self.outer_box.pack_end(footer, False, False, 4)

        self.show_all()

    def build_recorder_ui(self):
        self.clear_ui()

        self.status_label = Gtk.Label()
        self.status_label.set_use_markup(True)
        self.status_label.set_justify(Gtk.Justification.CENTER)
        self.status_label.set_line_wrap(True)
        self.status_label.set_line_wrap_mode(2)
        self.outer_box.pack_start(self.status_label, True, True, 0)

        self.info_label = Gtk.Label()
        self.info_label.set_justify(Gtk.Justification.CENTER)
        self.info_label.set_line_wrap(True)
        self.info_label.set_line_wrap_mode(2)
        self.outer_box.pack_start(self.info_label, True, True, 0)

        self.main_button = Gtk.Button(label="Start Recording")
        self.main_button.connect("clicked", self.on_main_button_clicked)
        self.outer_box.pack_start(self.main_button, False, False, 0)

        self.set_not_recording_state()
        self.show_all()

    def set_not_recording_state(self):
        self.status_label.set_markup("<span foreground='red'><b>Not Recording</b></span>")
        self.info_label.set_text("")
        self.main_button.set_label("Start Recording")

    def set_recording_state(self):
        self.status_label.set_markup("<span foreground='red'><b>Recording</b></span>")
        self.main_button.set_label("Stop Recording")

    def set_saved_state(self, length_text, size_text):
        safe_outfile = GLib.markup_escape_text(self.output_file)
        self.status_label.set_markup(
            f"<span foreground='green'><b>Successfully saved recording to {safe_outfile}\nwith a length of {length_text} and a file size of {size_text}!</b></span>"
        )
        self.info_label.set_text("")
        self.main_button.set_label("New Recording")

    def on_browse_clicked(self, _button):
        current_path = os.path.expanduser(self.path_entry.get_text().strip() or default_filename())
        current_dir = os.path.dirname(current_path) or os.path.expanduser("~")
        current_name = os.path.basename(current_path) or "recording.wav"

        dialog = Gtk.FileChooserDialog(
            title="Select Output File",
            parent=self,
            action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK
        )
        dialog.set_do_overwrite_confirmation(True)
        dialog.set_current_folder(current_dir)
        dialog.set_current_name(current_name)

        wav_filter = Gtk.FileFilter()
        wav_filter.set_name("WAV files")
        wav_filter.add_pattern("*.wav")
        dialog.add_filter(wav_filter)

        any_filter = Gtk.FileFilter()
        any_filter.set_name("All files")
        any_filter.add_pattern("*")
        dialog.add_filter(any_filter)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            chosen = dialog.get_filename()
            if chosen:
                self.path_entry.set_text(chosen)

        dialog.destroy()

    def on_file_ok_clicked(self, _button):
        path = os.path.expanduser(self.path_entry.get_text().strip())

        if not path:
            self.show_error("No File Selected", "Please choose or type an output file path.")
            return

        parent_dir = os.path.dirname(path) or "."
        if not os.path.isdir(parent_dir):
            self.show_error("Invalid Folder", f"The folder does not exist:\n{parent_dir}")
            return

        self.output_file = os.path.abspath(path)
        self.build_recorder_ui()

    def on_main_button_clicked(self, _button):
        label = self.main_button.get_label()

        if label == "Start Recording":
            self.start_recording()
        elif label == "Stop Recording":
            self.stop_recording()
        elif label == "New Recording":
            self.build_file_selection_ui()

    def start_recording(self):
        try:
            self.proc = subprocess.Popen(["pw-record", self.output_file])
        except FileNotFoundError:
            self.show_error("Missing Command", "pw-record is not installed or not in PATH.")
            return
        except Exception as e:
            self.show_error("Error", f"Could not start recording:\n{e}")
            return

        self.recording = True
        self.start_time = time.time()
        self.set_recording_state()
        self.update_timer()

        if self.timer_id is not None:
            GLib.source_remove(self.timer_id)
        self.timer_id = GLib.timeout_add(200, self.update_timer)

    def update_timer(self):
        if not self.recording or self.start_time is None:
            return False

        elapsed = int(time.time() - self.start_time)
        self.info_label.set_text(f"Recording length: {format_seconds(elapsed)}")
        return True

    def stop_recording(self):
        if self.proc is not None:
            try:
                self.proc.send_signal(signal.SIGTERM)
                self.proc.wait(timeout=3)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass

        self.proc = None
        self.recording = False

        if self.timer_id is not None:
            GLib.source_remove(self.timer_id)
            self.timer_id = None

        duration = int(time.time() - self.start_time) if self.start_time else 0
        length_text = format_seconds(duration)

        try:
            file_size = os.path.getsize(self.output_file)
        except OSError:
            file_size = 0

        size_text = human_size(file_size)
        self.set_saved_state(length_text, size_text)

    def on_delete_event(self, *_args):
        if self.recording:
            dialog = Gtk.MessageDialog(
                parent=self,
                flags=0,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text="Cancel Recording?"
            )
            dialog.format_secondary_text(
                "A recording is in progress.\nDo you want to stop it and exit without keeping it?"
            )
            response = dialog.run()
            dialog.destroy()

            if response != Gtk.ResponseType.YES:
                return True

            self.abort_recording_and_delete_file()

        Gtk.main_quit()
        return False

    def abort_recording_and_delete_file(self):
        if self.timer_id is not None:
            GLib.source_remove(self.timer_id)
            self.timer_id = None

        if self.proc is not None:
            try:
                self.proc.send_signal(signal.SIGTERM)
                self.proc.wait(timeout=3)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass

        self.proc = None
        self.recording = False

        try:
            if self.output_file and os.path.exists(self.output_file):
                os.remove(self.output_file)
        except OSError:
            pass

    def show_error(self, title, text):
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dialog.format_secondary_text(text)
        dialog.run()
        dialog.destroy()


def main():
    win = VoiceRecorderWindow()
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
