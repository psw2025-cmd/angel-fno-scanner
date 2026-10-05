using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Diagnostics;
using System.Threading;
using System.Windows.Forms;

public class Program {
    [StructLayout(LayoutKind.Sequential)]
    struct COPYDATASTRUCT {
        public IntPtr dwData;
        public int cbData;
        public IntPtr lpData;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct EVERYTHING_IPC_QUERYW {
        public int reply_hwnd;
        public int reply_copydata_message;
        public int search_flags;
        public int offset;
        public int max_results;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct EVERYTHING_IPC_ITEMW {
        public int flags;
        public int filename_offset;
        public int path_offset;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct EVERYTHING_IPC_LISTW {
        public int totfolders;
        public int totfiles;
        public int totitems;
        public int numfolders;
        public int numfiles;
        public int numitems;
        public int offset;
    }

    [DllImport("user32.dll", SetLastError = true)]
    static extern IntPtr OpenDesktop(string lpszDesktop, uint dwFlags, bool fInherit, uint dwDesiredAccess);

    [DllImport("user32.dll", SetLastError = true)]
    static extern bool SetThreadDesktop(IntPtr hDesktop);

    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
    static extern IntPtr FindWindow(string lpClassName, string lpWindowName);

    [DllImport("user32.dll", SetLastError = true)]
    static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, ref COPYDATASTRUCT lParam);

    [DllImport("user32.dll", SetLastError = true)]
    static extern bool ChangeWindowMessageFilterEx(IntPtr hWnd, uint msg, uint action, IntPtr pChangeFilterStruct);

    const uint MSGFLT_ALLOW = 1;
    const uint WM_COPYDATA = 0x004A;
    const int EVERYTHING_IPC_COPYDATAQUERYW = 2;
    const int EVERYTHING_IPC_ALLRESULTS = unchecked((int)0xFFFFFFFF);

    static List<string> results = new List<string>();
    static bool queryFinished = false;

    class ReplyWindow : NativeWindow {
        protected override void WndProc(ref Message m) {
            if (m.Msg == (int)WM_COPYDATA) {
                COPYDATASTRUCT cds = (COPYDATASTRUCT)Marshal.PtrToStructure(m.LParam, typeof(COPYDATASTRUCT));
                if (cds.cbData >= Marshal.SizeOf(typeof(EVERYTHING_IPC_LISTW))) {
                    EVERYTHING_IPC_LISTW list = (EVERYTHING_IPC_LISTW)Marshal.PtrToStructure(cds.lpData, typeof(EVERYTHING_IPC_LISTW));
                    int headerSize = Marshal.SizeOf(typeof(EVERYTHING_IPC_LISTW));
                    int itemSize = Marshal.SizeOf(typeof(EVERYTHING_IPC_ITEMW));
                    
                    for (int i = 0; i < list.numitems; i++) {
                        IntPtr itemPtr = new IntPtr(cds.lpData.ToInt64() + headerSize + (i * itemSize));
                        EVERYTHING_IPC_ITEMW item = (EVERYTHING_IPC_ITEMW)Marshal.PtrToStructure(itemPtr, typeof(EVERYTHING_IPC_ITEMW));
                        
                        IntPtr filePtr = new IntPtr(cds.lpData.ToInt64() + item.filename_offset);
                        IntPtr pathPtr = new IntPtr(cds.lpData.ToInt64() + item.path_offset);
                        
                        string file = Marshal.PtrToStringUni(filePtr);
                        string path = Marshal.PtrToStringUni(pathPtr);
                        
                        string fullPath;
                        if (string.IsNullOrEmpty(path)) {
                            fullPath = file;
                        } else {
                            fullPath = Path.Combine(path, file);
                        }
                        results.Add(fullPath);
                    }
                }
                queryFinished = true;
                Application.ExitThread();
                m.Result = new IntPtr(1);
                return;
            }
            base.WndProc(ref m);
        }
    }

    [STAThread]
    public static int Main(string[] args) {
        bool jsonOutput = false;
        int maxResults = EVERYTHING_IPC_ALLRESULTS;
        List<string> queryParts = new List<string>();

        for (int i = 0; i < args.Length; i++) {
            string a = args[i];
            if (a.Equals("-json", StringComparison.OrdinalIgnoreCase)) {
                jsonOutput = true;
            } else if (a.Equals("-n", StringComparison.OrdinalIgnoreCase) && i + 1 < args.Length) {
                int.TryParse(args[++i], out maxResults);
            } else if (a.StartsWith("-n:", StringComparison.OrdinalIgnoreCase)) {
                int.TryParse(a.Substring(3), out maxResults);
            } else if (a.Equals("-version", StringComparison.OrdinalIgnoreCase) || a.Equals("--version", StringComparison.OrdinalIgnoreCase)) {
                Console.WriteLine("Everything Search CLI Bridge (Ultra-Fast NTFS Index) v1.4");
                return 0;
            } else if (!a.StartsWith("-")) {
                queryParts.Add(a);
            }
        }

        string query = string.Join(" ", queryParts);
        int exitCode = 0;

        Thread t = new Thread(() => {
            // Switch to Default desktop
            IntPtr hDesktop = OpenDesktop("Default", 0, false, 0x01FF);
            if (hDesktop != IntPtr.Zero) {
                SetThreadDesktop(hDesktop);
            }

            // Find Everything IPC window
            IntPtr everythingHwnd = FindWindow("EVERYTHING_TASKBAR_NOTIFICATION", null);
            if (everythingHwnd == IntPtr.Zero) {
                try {
                    Process.Start(@"C:\Program Files\Everything\Everything.exe", "-startup");
                    Thread.Sleep(1000);
                    everythingHwnd = FindWindow("EVERYTHING_TASKBAR_NOTIFICATION", null);
                } catch {}
            }

            if (everythingHwnd == IntPtr.Zero) {
                Console.Error.WriteLine("Error: Everything IPC window not found. Please ensure Everything is running.");
                exitCode = 8;
                return;
            }

            ReplyWindow replyWnd = new ReplyWindow();
            CreateParams cp = new CreateParams();
            replyWnd.CreateHandle(cp);

            IntPtr replyHwnd = replyWnd.Handle;
            ChangeWindowMessageFilterEx(replyHwnd, WM_COPYDATA, MSGFLT_ALLOW, IntPtr.Zero);

            // Build query struct
            byte[] searchBytes = Encoding.Unicode.GetBytes(query + "\0");
            int queryHeaderSize = Marshal.SizeOf(typeof(EVERYTHING_IPC_QUERYW));
            int totalSize = queryHeaderSize + searchBytes.Length;
            IntPtr queryBuf = Marshal.AllocHGlobal(totalSize);

            EVERYTHING_IPC_QUERYW queryStruct = new EVERYTHING_IPC_QUERYW();
            queryStruct.max_results = maxResults;
            queryStruct.offset = 0;
            queryStruct.reply_copydata_message = 0;
            queryStruct.search_flags = 0;
            queryStruct.reply_hwnd = (int)replyHwnd.ToInt64();

            Marshal.StructureToPtr(queryStruct, queryBuf, false);
            Marshal.Copy(searchBytes, 0, new IntPtr(queryBuf.ToInt64() + queryHeaderSize), searchBytes.Length);

            COPYDATASTRUCT cds = new COPYDATASTRUCT();
            cds.dwData = new IntPtr(EVERYTHING_IPC_COPYDATAQUERYW);
            cds.cbData = totalSize;
            cds.lpData = queryBuf;

            // Forms Timer for 3-second timeout
            System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer();
            timer.Interval = 3000;
            timer.Tick += (sender, e) => {
                timer.Stop();
                Application.ExitThread();
            };
            timer.Start();

            // Send query
            SendMessage(everythingHwnd, WM_COPYDATA, replyHwnd, ref cds);
            Marshal.FreeHGlobal(queryBuf);

            Application.Run();
            timer.Dispose();
            replyWnd.DestroyHandle();
        });

        t.SetApartmentState(ApartmentState.STA);
        t.Start();
        t.Join();

        if (exitCode != 0) return exitCode;

        // Format Output
        if (jsonOutput) {
            StringBuilder sb = new StringBuilder();
            sb.Append("[\n");
            for (int i = 0; i < results.Count; i++) {
                string escaped = results[i].Replace("\\", "\\\\").Replace("\"", "\\\"");
                sb.Append("  \"").Append(escaped).Append("\"");
                if (i < results.Count - 1) sb.Append(",");
                sb.Append("\n");
            }
            sb.Append("]");
            Console.WriteLine(sb.ToString());
        } else {
            foreach (var r in results) {
                Console.WriteLine(r);
            }
        }

        return 0;
    }
}
